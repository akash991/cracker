import time
import json
import requests
import pandas as pd
import telegram_send
from cracker.configs import *

class Tracker():
    def __init__(self, assets):
        """
        Initialization function for this class

        INPUT:
            assets -> list of string
        RETURN:
            NONE

        Initializes with a list of coins that we are
        going to track.
        """
        self.assets = assets

    def collect_response(self, symbol):
        """
        Method to collect data from LUNARCrush

        INPUT:
            symbol -> list of strings
        RETURN:
            JSON Response

        Executes the REST api provided by LUNARCrush
        and fetch the response in JSON format. Then,
        return the 'data' field from the collected
        response.
        """
        data_list = []
        params = {
            "data":"assets",
            "key":APIKEY,
            "symbol":",".join(symbol)
        }
        response = requests.get(url=BASEURL, params=params)
        data_list = response.json()["data"]
        return data_list
    
    def create_json(self, data):
        """
        Method to create the JSON file.

        INPUT:
            data -> list of dictionary
        RETURN:
            NONE

        Executes collect_response() and extracts
        name, symbol and price for each coin present
        in the list. Then, dump that data in the form
        of a JSON file.
        """
        self.last_notification_time = time.time()
        new_data = []
        for entry in data:
            temp = {}
            temp["name"] = entry["name"]
            temp["symbol"] = entry["symbol"]
            temp["start_price"] = entry["price"]
            temp["current_price"] = entry["price"]
            new_data.append(temp)
        with open(os.path.join(WORKDIR, "data/dump.json"), "w") as file:
            json.dump(new_data, file)

    def update_json(self, data):
        """
        Method to update the json file.

        INPUT:
            data -> list of dictionary
        RETURN:
            NONE

        Loads the existing JSON file and updates
        the 'current_price' and 'percent_change' for 
        all coins then dump the updated dictionary in
        the same JSON file.
        """
        old_data = None
        with open(os.path.join(WORKDIR, "data/dump.json")) as file:
            old_data = json.load(file)
        current_time = time.time()
        for old, current in zip(old_data, data):
            old["current_price"] = current["price"]
            old["percent_change"] = (old["current_price"] - old["start_price"]) * 100.0 / old["start_price"]
        with open(os.path.join(WORKDIR, "data/dump.json"), "w") as file:
            json.dump(old_data, file)

    def send_notification(self, messages):
        """
        Method to send notification over telegram

        INPUT:
            messages -> list of strings
        RETURN:
            NONE

        Uses the method telegram_send.send() to send
        message(s) over Telegram.
        """
        telegram_send.send(messages=messages)

    def fetch_performers(self, json_file, entries=5):
        """
        Method to fetch a list of the top performers.

        INPUT:
            json_file -> string
            entries -> integer

        Loads the json file to create a DataFrame and derive a
        list of top performers from it
        """
        df = pd.read_json(json_file)
        return df.sort_values("percent_change", ascending=False).head(entries)

    def collect_alerts(self):
        """
        Method to collect alerts.

        INPUT:
            None
        RETURN:
            list of strings

        Opens the json file to collect the list of records.
        Calls the fetch_performers API that returns a list of
        the top performers in the given interval.
        If the gap between the current and the last data
        collection is more than 1 hour, collect the coins that
        are being tracked and draft the telegram message using
        the tracked coin and top performers.
        """
        hour_alerts = []
        hour_flag = False

        with open(os.path.join(WORKDIR, "data/dump.json")) as file:
            json_data = json.load(file)

        top_performers = self.fetch_performers(os.path.join(WORKDIR,"data/dump.json"))
        
        current_time = time.time()
        last_notification_at = self.last_notification_time
        
        if (current_time - last_notification_at) >= 3600:
            hour_flag = True
            self.last_notification_time = current_time
        
        for entry in json_data:
            if entry["symbol"] in self.assets and hour_flag==True:
                hour_alerts.append(entry)

        if hour_flag:
            return self.draft_telegram_message(hour_alerts, top_performers)

    def draft_telegram_message(self, hour_alert, top_performers):
        """
        Method to draft the telegram message.

        INPUT:
            hour_alert -> list of dictionaries
            top_performers -> list of dictionaries
        RETURN:
            message -> list of strings

        Parse through the list of hourly alerts and draft
        a message consisting of the Name, Symbol, Price and
        Percent Change for all the coins that are being tracked.

        Parse through the list of top performers and draft
        a message consisting of Name, Symbol and percent change in
        1 hour.
        """
        messages = []
        message = "HOURLY ALERTS\n"
        for entry in hour_alert:
            message += "{}:{}\n".format("Name",entry["name"])
            message += "{}:{}\n".format("Symbol", entry["symbol"])
            message += "{}:{}\n".format("Price", entry["current_price"])
            message += "{}:{:.3f}\n\n".format("Percent Change", entry["percent_change"])
        messages.append(message)

        message = "TOP PERFORMERS\n"
        for val in top_performers.values:
            message += "{}:{}\n".format("Name", val[0])
            message += "{}:{}\n".format("Symbol", val[1])
            message += "{}:{:.3f}\n\n".format("1hr Change", val[-1])
        messages.append(message)
        return messages

    def start_tracker(self, interval=60*60):
        """
        Method to start tracking the coins

        INPUT:
            interval -> integer
        RETURN
            NONE

        Starts tracking specific coins and send
        notification at regular interval
        """
        data = self.collect_response(self.assets)
        self.create_json(data)
        while True:
            data = self.collect_response(self.assets)
            self.update_json(data)
            alerts = self.collect_alerts()
            if not alerts is None and len(alerts) > 0:
                self.send_notification(alerts)
            time.sleep(interval)
