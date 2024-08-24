import sys
import os
import logging
from ib_insync import *

# Add the tbot-tradingboat directory to the Python path
sys.path.append('/home/tbot/develop/github/tbot-tradingboat/src')

from tbot_tradingboat.utils.tbot_env import shared
from tbot_tradingboat.utils.tbot_utils import strtobool

# Configure logging to inherit TBOT's configuration
logging.basicConfig(level=shared.loglevel, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Connect to Interactive Brokers
ib = IB()

def connect_to_ib():
    try:
        ib.connect(shared.ibkr_addr, int(shared.ibkr_port), clientId=2)  # Static clientId set to 2
        logger.info("From Close-All: Connected to IBKR successfully.")
    except Exception as e:
        logger.error(f"From Close-All: Failed to connect to IBKR: {e}")
        sys.exit(1)

# Global variables
initial_net_liq = None
positions_closed = False  # To prevent multiple order placements

# Function to close all positions
def close_all_positions():
    global positions_closed
    if positions_closed:
        logger.info("From Close-All: Positions have already been closed. Skipping this action.")
        return

    positions = ib.positions()
    for position in positions:
        contract = position.contract
        quantity = position.position

        # If long position, sell it; if short position, buy to cover
        if quantity > 0:
            order = MarketOrder('SELL', quantity)
        else:
            order = MarketOrder('BUY', -quantity)

        try:
            trade = ib.placeOrder(contract, order)
            logger.info(f"From Close-All: Placing order to close position in {contract.symbol}, Quantity: {quantity}")
        except Exception as e:
            logger.error(f"From Close-All: Error placing order for {contract.symbol}: {e}")

    # Set flag to avoid closing positions multiple times
    positions_closed = True
    logger.info("From Close-All: All positions have been closed.")

# Callback function to handle account updates
def on_account_value(accountValue):
    global initial_net_liq, positions_closed
    # Get the Net Liquidation value from the update
    if accountValue.tag == 'NetLiquidation':
        current_net_liq = float(accountValue.value)
        
        if initial_net_liq is None:
            initial_net_liq = current_net_liq
            logger.info(f"From Close-All: Initial Net Liquidation Value: {initial_net_liq}")
            return

        # Calculate the percentage change
        percentage_change = ((current_net_liq - initial_net_liq) / initial_net_liq) * 100
        logger.info(f"From Close-All: Current Net Liquidation Value: {current_net_liq}")
        logger.info(f"From Close-All: Unrealized P&L Percentage Change: {percentage_change}%")

        # Check if the unrealized P&L is down by 1% or more and if positions haven't been closed yet
        if percentage_change <= -1.0 and not positions_closed:
            logger.warning("From Close-All: Unrealized P&L is down 1% or more. Closing all positions.")
            close_all_positions()
            ib.disconnect()

def main():
    # Attempt to connect to IBKR
    connect_to_ib()

    # Subscribe to account updates
    ib.accountValueEvent += on_account_value
    
    # Keep the connection alive and listen for events
    try:
        logger.info("From Close-All: Starting event loop.")
        ib.run()
    except KeyboardInterrupt:
        logger.info("From Close-All: Script interrupted by user. Closing connection.")
    finally:
        if ib.isConnected():
            ib.disconnect()
        logger.info("From Close-All: Disconnected from IBKR.")

if __name__ == "__main__":
    main()
