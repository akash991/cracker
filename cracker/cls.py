import time
import json
import requests
import pandas as pd
import telegram_send
from configs import *

class Base():
    def __init__(self, assets):
        self.assets = assets

    def collect_response(self):
        with open("/home/akash/Desktop/Cracker/data/binance_btc_pair.txt") as file:
            symbol = file.read().split("\n")
        data_list = []
        for _ in (symbol[:150], symbol[150:]):
            params = {
                "data":"assets",
                "key":APIKEY,
                "symbol":",".join(_)
            }
            response = requests.get(url=BASEURL, params=params)
            data_list += response.json()["data"]
        return data_list
    
    def create_json(self):
        data = self.collect_response()
        self.last_notification_time = time.time()
        new_data = []
        for entry in data:
            temp = {}
            temp["name"] = entry["name"]
            temp["symbol"] = entry["symbol"]
            temp["start_price"] = entry["price"]
            temp["current_price"] = entry["price"]
            new_data.append(temp)
        with open("data/dump.json", "w") as file:
            json.dump(new_data, file)

    def update_json(self):
        old_data = None
        with open("data/dump.json") as file:
            old_data = json.load(file)
        current_time = time.time()
        data = self.collect_response()
        for old, current in zip(old_data, data):
            old["current_price"] = current["price"]
            old["percent_change"] = (old["current_price"] - old["start_price"]) * 100.0 / old["start_price"]
        with open("data/dump.json", "w") as file:
            json.dump(old_data, file)

    def send_notification(self, messages):
        telegram_send.send(messages=messages)

    def fetch_performers(self, json_file):
        df = pd.read_json(json_file)
        return df.sort_values("percent_change", ascending=False).head()

    def collect_alerts(self):
        hour_alerts = []
        hour_flag = False

        with open("data/dump.json") as file:
            json_data = json.load(file)

        top_performers = self.fetch_performers("data/dump.json")
        
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

if __name__ == "__main__":
    assets = ["NAV", "VIA"]
    base = Base(assets=assets)
    base.create_json()
    while True:
        base.update_json()
        alerts = base.collect_alerts()
        if not alerts is None and len(alerts) > 0:
            base.send_notification(alerts)
        time.sleep(60*60)