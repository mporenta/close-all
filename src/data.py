import datetime
import logging
import ib_insync
from ib_insync  import *
import os

# Setup logging with a valid path
log_file = os.path.join(os.path.dirname(__file__), 'close_all_log.txt')
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Connect to IB Gateway
logging.info('Connecting to IB Gateway...')
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
logging.info('Connected to IB Gateway.')

def get_last_price(contract):
    logging.info(f'Requesting market data for contract: {contract.symbol}')
    
    # Request market data directly
    ticker = ib.reqMktData(contract, '', False, False)
    
    # Increase the wait time to give IB Gateway enough time to return market data
    ib.sleep(5)  # Increased wait time for live data

    if not isNan(ticker.last):
        logging.info(f'Found market data for {contract.symbol}: Last price is {ticker.last}')
        return ticker.last
    else:
        logging.warning(f'No last price available for {contract.symbol}. Fetching historical data...')
        
        # Get historical data if after hours or during weekends
        now = datetime.datetime.now().strftime('%Y%m%d %H:%M:%S')
        
        # Request historical data over the last 2 days to ensure we capture prices from Friday
        bars = ib.reqHistoricalData(
            contract, endDateTime=now, durationStr='2 D',
            barSizeSetting='1 day', whatToShow='TRADES', useRTH=False)

        if bars:
            logging.info(f'Found historical data for {contract.symbol}: Last historical close price is {bars[-1].close}')
            return bars[-1].close  # Return last historical price
        else:
            logging.error(f'No historical data available for {contract.symbol}.')
            return None

def main():
    logging.info('Fetching positions...')
    # Get all positions
    positions = ib.positions()
    logging.info(f'Found {len(positions)} positions.')

    for position in positions:
        contract = position.contract
        logging.info(f'Processing position for {contract.symbol}')
        last_price = get_last_price(contract)
        
        if last_price is not None:
            logging.info(f'Position: {contract.symbol}, Last Price: {last_price}')
            print(f"Position: {contract.symbol}, Last Price: {last_price}")
        else:
            logging.error(f'Failed to retrieve last price for {contract.symbol}')
            print(f"Position: {contract.symbol}, Last Price: None")

if __name__ == "__main__":
    logging.info('Script started.')
    main()
    logging.info('Script finished.')

# Disconnect from IB Gateway after the script ends
logging.info('Disconnecting from IB Gateway...')
ib.disconnect()
logging.info('Disconnected from IB Gateway.')
