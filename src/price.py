import datetime
import logging
import pandas as pd
import  ib_async
from ib_async import *

import os
import math  # Import the math module to use isnan

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
ib.connect('127.0.0.1', 4002, clientId=6666)
logging.info('Connected to IB Gateway.')



ib.reqMarketDataType(4)  # Use free, delayed, frozen data
contract = Stock('NVDA', 'SMART', 'USD')
bars = ib.reqHistoricalData(
    contract, endDateTime='', durationStr='30 D',
    barSizeSetting='1 day', whatToShow='ADJUSTED_LAST', useRTH=True)

# convert to pandas dataframe (pandas needs to be installed):
df = util.df(bars)
print(df)