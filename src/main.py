
from ib_insync import *

# Connect to Interactive Brokers with clientId=2
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=2)

# Global variable to store the initial Net Liquidation value
initial_net_liq = None

# Function to close all positions
def close_all_positions():
    positions = ib.positions()
    for position in positions:
        contract = position.contract
        quantity = position.position
        
        # If long position, sell it; if short position, buy to cover
        if quantity > 0:
            order = MarketOrder('SELL', quantity)
        else:
            order = MarketOrder('BUY', -quantity)
        
        # Place the order
        trade = ib.placeOrder(contract, order)
        print(f"Closing position in {contract.symbol}, Quantity: {quantity}")

# Callback function to handle account updates
def on_account_value(accountValue):
    global initial_net_liq

    # Get the Net Liquidation value from the update
    if accountValue.tag == 'NetLiquidation':
        current_net_liq = float(accountValue.value)

        # If this is the first time, set the initial Net Liquidation value
        if initial_net_liq is None:
            initial_net_liq = current_net_liq
            print(f"Initial Net Liquidation Value: {initial_net_liq}")
            return

        # Calculate the percentage change
        percentage_change = ((current_net_liq - initial_net_liq) / initial_net_liq) * 100
        print(f"Current Net Liquidation Value: {current_net_liq}")
        print(f"Unrealized P&L Percentage Change: {percentage_change}%")

        # Check if the unrealized P&L is down by 1% or more
        if percentage_change <= -1.0:
            print("Unrealized P&L is down 1% or more. Closing all positions.")
            close_all_positions()
            ib.disconnect()

# Subscribe to account updates
ib.accountValueEvent += on_account_value

# Keep the connection alive and listen for events
ib.run()
