import yfinance
import matplotlib.pyplot as plt
from datetime import datetime
import time
import websocket
import json
import alpaca_trade_api as tradeapi
import requests


api_key = 'AKJ9A771I0NI20D4AX1D'
api_secret = 'd3DAz3dAavtH6MP8aAYv5mrPDyLHNF8swvzAexNZ'
url1 = 'wss://stream.data.alpaca.markets/v1beta3/crypto/us'
url2 = 'https://api.alpaca.markets/v2/orders'

#1018

anteil =0.026592695

cashflow = 0
start_price = 100
start_value = 100

# Lists to store data for plotting
timestamps = []
prices = []
values = []
cashflows = []


def on_message(ws, message):
    data = json.loads(message)
    if data and isinstance(data, list) and len(data) > 0:
        first_element = data[0]
        if 'T' in first_element and first_element['T'] == 'q' and 'S' in first_element and first_element['S'] == 'BTC/USD' and 'bp' in first_element:
            current_price = first_element['bp']
            print(current_price)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Closed WebSocket connection")

def on_open(ws):
    auth_message = {"action": "auth", "key": api_key, "secret": api_secret}
    ws.send(json.dumps(auth_message))

    subscribe_message = {"action": "subscribe", "quotes": ["BTC/USD"]}
    ws.send(json.dumps(subscribe_message))

def getBitcoin():
    ws = websocket.WebSocketApp(url1, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()

def get_gold_price():
    try:
        bitcoin = yfinance.Ticker('BTC-USD')
        daten = bitcoin.basic_info

        # Überprüfen, ob 'last_price' im Dictionary vorhanden ist
        if daten['last_price'] is not None:
            price = daten['last_price']
            print(price)
            return price
        else:
            return None

    except Exception as e:
        print(f"Fehler beim Abrufen des Goldpreises: {e}")
        return None

def trade_eat_the_win():
    global start_price, start_value, anteil, cashflow

    current_price = get_gold_price()

    if current_price is not None:
        if start_price is None:
            start_price = current_price
            start_value = start_price * anteil
            prices.append(start_price)
            values.append(start_value)
            cashflows.append(cashflow)
            timestamps.append(datetime.now())

    if current_price is not None:
        current_value = current_price * anteil
        harvest = current_value - start_value

        # Update data for plotting
        timestamps.append(datetime.now())
        prices.append(current_price)
        values.append(current_value)
        cashflows.append(cashflow)

        if harvest > 0.002:
            anteil -= harvest / current_price

            cashflow += harvest
            print("Sell")
            print("Anteil:", anteil)
            print("Cashflow:", cashflow)
            order_data = {"symbol": "BTC/USD", "qty": harvest / current_price, "side": "sell", "type": "market", "time_in_force": "ioc"}
            headers = {'Apca-Api-Key-Id': api_key,'Apca-Api-Secret-Key': api_secret, 'Content-Type': 'application/json'}
            response = requests.post(url2, headers=headers, json=order_data)
            if response.status_code == 200:
                print("Marktorder erfolgreich platziert und sofort ausgeführt.")
            else:
                print(f"Fehler bei der Auftragserteilung. Statuscode: {response.status_code}, Antwort: {response.text}")

        if harvest < -1000:
            anteil -= harvest / current_price

            cashflow += harvest
            print("Buy")
            print("Anteil:", anteil)
            print("Cashflow:", cashflow)
            order_data = {"symbol": "BTC/USD", "qty": -1*(harvest/current_price), "side": "buy", "type": "market", "time_in_force": "ioc"}
            headers = {'Apca-Api-Key-Id': api_key,'Apca-Api-Secret-Key': api_secret, 'Content-Type': 'application/json'}
            response = requests.post(url2, headers=headers, json=order_data)
            if response.status_code == 200:
               print("Marktorder erfolgreich platziert und sofort ausgeführt.")
            else:
              print(f"Fehler bei der Auftragserteilung. Statuscode: {response.status_code}, Antwort: {response.text}")

        #plot_real_time_data()

def plot_real_time_data():
    plt.clf()  # Clear the current figure

    # Plot current price and value as smaller points in the first subplotc
    plt.subplot(2, 1, 1)
    plt.scatter(timestamps, prices, label='Current Price', marker='o', color='blue', s=1)
    plt.scatter(timestamps, values, label='Current Value', marker='o', color='orange', s=1)
    plt.title('Real-Time Price and Value')
    plt.xlabel('Time')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True)

    # Plot cashflow as smaller points in the second subplot
    plt.subplot(2, 1, 2)
    plt.scatter(timestamps, cashflows, label='Cashflow', marker='o', color='green', s=1)
    plt.title('Real-Time Cashflow')
    plt.xlabel('Time')
    plt.ylabel('Cashflow')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.draw()  # Redraw the plot
    plt.pause(0.0001)  # Pause for a short time to allow the plot to update


def main():

     while True:
        trade_eat_the_win()
        






##getBitcoin()



if __name__ == "__main__":
    main()
