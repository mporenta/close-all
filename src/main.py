import sys
import logging
import numpy as np
from ib_insync import *
import time
import threading

# Hardcoded IBKR configuration
ibkr_addr = "localhost"
ibkr_port = 4002
ibkr_clientid = 270

# Define TEST_MODE
TEST_MODE = 1  # Set to 1 to enable NVDA test logic, 0 to disable

# Configure logging to a hardcoded file path
logging.basicConfig(
    level="INFO", 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler("/home/close_all_log.txt"),
        logging.FileHandler("close_all_log.txt"),
        logging.StreamHandler(sys.stdout)  # Also log to stdout
    ]
)
logger = logging.getLogger(__name__)

# Connect to Interactive Brokers
ib = IB()

# Global variables
positions_closed = False
positions_closed_lock = threading.Lock()

def connect_to_ib(max_retries=10, delay=10):
    retries = 0
    while retries < max_retries:
        try:
            ib.connect(ibkr_addr, ibkr_port, clientId=ibkr_clientid)
            logger.info("From Close-All: Connected to IBKR successfully.")
            return True
        except Exception as e:
            retries += 1
            logger.error(f"From Close-All: Failed to connect to IBKR. Attempt {retries}/{max_retries}: {e}")
            time.sleep(delay)

    logger.error("From Close-All: Failed to connect to IBKR after multiple attempts. Exiting...")
    sys.exit(1)

def set_initial_net_liq():
    global initial_net_liq
    try:
        account_summary = ib.accountSummary()
        initial_net_liq = float([item for item in account_summary if item.tag == 'NetLiquidation'][0].value)
        logger.info(f"From Close-All: Initial Net Liquidation Value set to {initial_net_liq}")
    except Exception as e:
        logger.error(f"From Close-All: Error setting initial net liquidation value: {e}")
        sys.exit(1)

def close_all_positions():
    global positions_closed
    with positions_closed_lock:
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
                trade_status = ib.waitOnUpdate(timeout=10)  # Wait for the order to complete
                if trade.orderStatus.status == 'Filled':
                    logger.info(f"From Close-All: Successfully closed position in {contract.symbol}, Quantity: {quantity}")
                else:
                    logger.error(f"From Close-All: Order for {contract.symbol} did not complete in time.")
            except Exception as e:
                logger.error(f"From Close-All: Error placing order for {contract.symbol}: {e}")

        positions_closed = True
        logger.info("From Close-All: All positions have been closed.")

def close_nvda_position_with_test_logic():
    logger.info("From Test: Starting test logic for NVDA position closure.")

    # Fetch all positions
    positions = ib.positions()
    logger.info(f"From Test: Retrieved positions: {positions}")

    for position in positions:
        logger.info(f"From Test: Evaluating position: {position.contract.symbol}")

        # Check if the position is NVDA
        if position.contract.symbol == "NVDA":
            logger.info("From Test: NVDA position detected, proceeding with closure logic.")

            # Create a simplified contract using only the conId
            contract_with_only_id = Contract(conId=position.contract.conId)
            logger.info(f"From Test: Created contract with only conId: {contract_with_only_id}")

            # Qualify the simplified contract
            ib.qualifyContracts(contract_with_only_id)
            logger.info(f"From Test: Qualified contract: {contract_with_only_id}")

            # Fetch the market data for NVDA
            ticker = ib.reqMktData(contract_with_only_id, '', False, False)
            ib.sleep(1)  # Allow time for price to be fetched
            logger.info("From Test: Requesting market data for NVDA.")

            # Wait until we get a valid last price, with a timeout
            timeout = 10
            start_time = time.time()
            while ticker.last is None and (time.time() - start_time) < timeout:
                logger.info("From Test: Waiting for valid last price for NVDA...")
                ib.sleep(0.5)

            # Check if we successfully got a last price, otherwise try midpoint
            last_price = ticker.last
            if not last_price or last_price != last_price:  # Detect NaN or None
                last_price = ticker.midpoint()
                logger.info(f"From Test: No valid last price available, using midpoint: {last_price}")

            # If still no valid price, fall back to historical data
            if not last_price or last_price != last_price:
                logger.warning("From Test: Could not retrieve a valid last price or midpoint. Fetching historical data.")
                bars = ib.reqHistoricalData(
                    contract_with_only_id, endDateTime='', durationStr='1 D',
                    barSizeSetting='1 min', whatToShow='ADJUSTED_LAST', useRTH=True
                )
                
                if bars:
                    last_price = bars[-1].close  # Use the last closing price from historical data
                    logger.info(f"From Test: Historical data fallback used, last price from historical data: {last_price}")
                else:
                    logger.error("From Test: Failed to retrieve historical data. Aborting.")
                    return

            logger.info(f"From Test: Last price for NVDA retrieved: {last_price}")

            # Ensure tick size is defined, else use a default value
            tick_size = 0.01  # Default tick size as 'minTick' attribute isn't available
            logger.info(f"From Test: Using tick size: {tick_size}")

            if position.position > 0:
                # Long position, place sell limit order 2 ticks below last price
                limit_price = last_price - 2 * tick_size
                logger.info(f"From Test: Long position detected. Calculated sell limit price: {limit_price}")
                order = LimitOrder('SELL', position.position, limit_price)
                logger.info(f"From Test: Created sell limit order for {position.position} shares at {limit_price}")
            else:
                # Short position, place buy to cover limit order 2 ticks above last price
                limit_price = last_price + 2 * tick_size
                logger.info(f"From Test: Short position detected. Calculated buy limit price: {limit_price}")
                order = LimitOrder('BUY', -position.position, limit_price)
                logger.info(f"From Test: Created buy limit order for {-position.position} shares at {limit_price}")

            # Check for NaN in limit price
            if limit_price is None or limit_price != limit_price:  # Detects NaN
                logger.error("From Test: Limit price is invalid (NaN). Aborting.")
                return

            # Place the limit order
            try:
                trade = ib.placeOrder(contract_with_only_id, order)
                logger.info(f"From Test: Placed limit order for NVDA, Quantity: {position.position}, Limit Price: {limit_price}")
                ib.sleep(10)  # Wait for 10 seconds to see if the order fills
                
                if trade.orderStatus.status == 'Filled':
                    logger.info("From Test: NVDA limit order filled.")
                else:
                    logger.info("From Test: NVDA limit order not filled, sending market order.")
                    
                    # Send a market order to close the position
                    if position.position > 0:
                        market_order = MarketOrder('SELL', position.position)
                        logger.info(f"From Test: Created market order to SELL {position.position} shares.")
                    else:
                        market_order = MarketOrder('BUY', -position.position)
                        logger.info(f"From Test: Created market order to BUY {-position.position} shares.")
                    
                    ib.placeOrder(contract_with_only_id, market_order)
                    logger.info("From Test: NVDA market order placed to close position.")
            except Exception as e:
                logger.error(f"From Test: Error executing NVDA order: {e}")



# Triggered on order execution or trade events
def update_data_and_evaluate_risk():
    try:
        account_values = ib.accountValues()
        portfolio = ib.portfolio()
        positions = ib.positions()
        trades = ib.trades()
        executions = ib.executions()

        unrealized_pnl = sum(pnl.unrealizedPnL for pnl in ib.pnl())
        realized_pnl = sum(pnl.realizedPnL for pnl in ib.pnl())
        total_pnl = np.sum([unrealized_pnl, realized_pnl])

        logger.info(f"From Close-All: Total Unrealized PnL: {unrealized_pnl}")
        logger.info(f"From Close-All: Total Realized PnL: {realized_pnl}")
        logger.info(f"From Close-All: Total PnL for the day: {total_pnl}")

        if unrealized_pnl <= -0.01 * initial_net_liq and not positions_closed:
            logger.warning("From Close-All: Unrealized PnL loss exceeds 1%. Closing all positions.")
            close_all_positions()

    except Exception as e:
        logger.error(f"From Close-All: Error while updating data and evaluating risk: {e}")

def on_order_event(trade):
    update_data_and_evaluate_risk()

def on_position_event(position):
    update_data_and_evaluate_risk()

def on_pnl_update(pnl):
    update_data_and_evaluate_risk()

def main():
    # Connect to IBKR
    connect_to_ib()

    # Set the initial net liquidation value
    set_initial_net_liq()

    # Test logic for NVDA
    if TEST_MODE == 1:
        close_nvda_position_with_test_logic()

    # Subscribe to necessary events
    ib.orderStatusEvent += on_order_event
    ib.execDetailsEvent += on_order_event
    ib.positionEvent += on_position_event
    ib.pnlEvent += on_pnl_update

    try:
        ib.run()
    except KeyboardInterrupt:
        logger.info("From Close-All: Script interrupted by user. Closing connection.")
    finally:
        if ib.isConnected():
            ib.disconnect()
        logger.info("From Close-All: Disconnected from IBKR.")

if __name__ == "__main__":
    main()
