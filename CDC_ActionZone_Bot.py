import pandas as pd
import binance
import requests
import datetime
import time
import json
from binance.client import BinanceAPIException

def get_top_coins(API_KEY):
    headers = {
        'X-CMC_PRO_API_KEY': API_KEY
    }
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    r = requests.get(url, headers=headers)
    coins = []
    if r.status_code == 200:
        data = r.json()
        for d in data['data']:
            coins.append({
                'symbol': d['symbol'],
                'rank': d['cmc_rank'],
                'market_cap': d['quote']['USD']['market_cap']
            })
    return coins

def get_ticker_price():
    FUTURE_URL = 'https://fapi.binance.com/fapi/v1'
    r = requests.get(FUTURE_URL + '/ticker/price')
    return r.json()

def get_binance_symbol():
    binance_symbols = set()
    for symbol in get_ticker_price():
        if symbol["symbol"][-4:] == 'USDT':
            binance_symbols.add(symbol["symbol"][:-4])
    return binance_symbols

def get_trade_coins(coins, symbols, limit, only_symbol=False):
    trade_coins = []
    for coin in coins:
        if coin['symbol'] in symbols:
            if only_symbol:
                trade_coins.append(coin['symbol'])
            else:
                trade_coins.append(coin)
            if len(trade_coins) == limit:
                break
    return trade_coins

def get_signal(symbol, tf="1d", prd1=12, prd2=26):
    try:
        FUTURE_URL = 'https://fapi.binance.com/fapi/v1'
        params = {
            'symbol': symbol+'USDT',
            'limit': 500,
            'interval': tf
        }
        r = requests.get(FUTURE_URL + '/klines', params=params)
        df = pd.DataFrame(r.json(), columns=['Open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_time', 'Quote_asset_volume',
        'Number_of_trades', 'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore']).drop(columns=['Close_time', 'Quote_asset_volume',
        'Number_of_trades', 'Taker_buy_base_asset_volume', 'Taker_buy_quote_asset_volume', 'Ignore'])
        df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype('double')
        ema1 = df["Close"].ewm(span=prd1, adjust=False).mean()
        ema2 = df["Close"].ewm(span=prd2, adjust=False).mean()
        ema1_0, ema1_1 = ema1[df.shape[0]-2], ema1[df.shape[0]-3]
        ema2_0, ema2_1 = ema2[df.shape[0]-2], ema2[df.shape[0]-3]
        bullish_signal = (ema1_0 >= ema2_0) and (ema1_1 < ema2_1)
        bearish_signal = (ema1_0 <= ema2_0) and (ema1_1 > ema2_1)
        swing_low = df["Low"][(df["Low"] < df["Low"].shift(1)) & (df["Low"] < df["Low"].shift(-1))]
        swing_low = swing_low[swing_low.index >= df.shape[0]-prd2-1].min()
        current_price = df["Close"][df.shape[0]-1]
        size_ratio = (1 / (current_price - swing_low))
    except Exception as e:
        print(params)
        print(symbol)
        print(df)
        print(psymbol)
        raise e
    return bullish_signal, bearish_signal, size_ratio, swing_low, current_price

def log(log_file, *args):
    s = ' '.join([ str(x) for x in [f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:", *args] ])
    print(s)
    with open(log_file, "a") as file_object:
        file_object.write(str(s)+'\n')

def get_actions(trade_coins):
    actions = []
    for coin in trade_coins:
        bullish_signal, bearish_signal, size_ratio, swing_low, current_price = get_signal(coin)
        if bullish_signal:
            actions.append({
                'symbol': coin,
                'action': 'buy',
                'stop_loss': swing_low,
                'current_price': current_price,
                'size_ratio': size_ratio
            })
        elif bearish_signal:
            actions.append({
                'symbol': coin,
                'action': 'sell',
                'current_price': current_price
            })
    return actions

def get_openning_position(client):
    positions = []
    psymbol = {}
    all_positions = client.futures_position_information()
    for position in all_positions:
        if float(position['positionAmt']) > 0:
            psymbol[position['symbol'][:-4]] = float(position['positionAmt'])
            for key, val in position.items():
                if type(val) == type(str()):
                    if val.isdigit():
                        position[key] = int(val)
                    else:
                        try:
                            position[key] = float(val)
                        except ValueError:
                            pass
            positions.append(position)
    return positions, psymbol

def get_summary(p):
    df = pd.DataFrame(p, columns=['symbol', 'positionAmt', 'entryPrice', 'markPrice', 'unRealizedProfit',
       'liquidationPrice', 'leverage', 'maxNotionalValue', 'marginType',
       'isolatedMargin', 'isAutoAddMargin', 'positionSide', 'notional',
       'isolatedWallet', 'updateTime'])
    return {
        "total_position_size_usd": (df['positionAmt'] * df['entryPrice']).sum(),
        "total_margin": df["isolatedWallet"].sum(),
        "unrealized_profit": df["unRealizedProfit"].sum()
    }
    
def get_precision(client): ###################
    pair_precision = {}
    for pair in client.futures_exchange_info()['symbols']:
        pair_precision[pair['symbol']] = pair['quantityPrecision']
    return pair_precision

def execute_action(client, action, risk=None, risk_safty_factor=None, pair_precision=None, psymbol=None):
    res = None
    pair_symbol = action['symbol'] + 'USDT'
    if action['action'] == 'buy':
        precision = pair_precision[pair_symbol]
        try:
            client.futures_change_margin_type(symbol=pair_symbol, marginType="ISOLATED")
        except BinanceAPIException as e:
            if str(e) != "APIError(code=-4046): No need to change margin type.":
                raise e
        client.futures_change_leverage(symbol=pair_symbol, leverage=int(1 / (risk_safty_factor * (1-action['stop_loss']/action['current_price']))))
        quantity = int((action['size_ratio'] * risk) * (10**precision)) / (10**precision)
        if quantity > 0:
            try:
                res = client.futures_create_order(
                    symbol=pair_symbol,
                    side=client.SIDE_BUY,
                    type=client.FUTURE_ORDER_TYPE_MARKET,
                    quantity=quantity
                )
                res1 = client.futures_create_order(
                    symbol=pair_symbol, 
                    side=client.SIDE_SELL,
                    type=client.FUTURE_ORDER_TYPE_STOP_MARKET, 
                    closePosition=True, 
                    stopPrice=action['stop_loss']
                )
            except BinanceAPIException as e:
                log(log_file, "buy error", e)
                res = "buy error"
                res1 = None
        else:
            res = f"{pair_symbol} quantity is 0"
            res1 = None
        return res, res1
    else:
        if action['symbol'] in psymbol:
            close_quantity = psymbol[action['symbol']]
            try:
                res = client.futures_create_order(
                    symbol=pair_symbol,
                    side=client.SIDE_SELL,
                    type=client.ORDER_TYPE_MARKET,
                    quantity=close_quantity,
                    reduceOnly=True
                )
            except BinanceAPIException as e:
                if str(e).strip() != "APIError(code=-2022): ReduceOnly Order is rejected.":
                    raise e
        return res

def clear_sl(client, psymbol):
    all_res = []
    open_orders = client.futures_get_open_orders()
    for order in open_orders:
        if order['type'] == 'STOP_MARKET':
            if order['symbol'][:-4] not in psymbol:
                all_res.append(client.futures_cancel_all_open_orders(symbol=order['symbol']))
    return all_res

def show_balance(client):
    for asset in client.futures_account_balance():
        if asset['asset'] == 'USDT':
            log(log_file, 'Balance:\n', asset)

def show_position(positions):
    log(log_file, "Positions:\n", pd.DataFrame(positions, columns=['symbol', 'positionAmt', 'entryPrice', 'markPrice', 'unRealizedProfit',
        'liquidationPrice', 'leverage', 'maxNotionalValue', 'marginType',
        'isolatedMargin', 'isAutoAddMargin', 'positionSide', 'notional',
        'isolatedWallet', 'updateTime']
    )[["symbol", "positionAmt", "entryPrice", "markPrice", "unRealizedProfit", "liquidationPrice", "leverage", "marginType", "isolatedWallet"]].to_string())

with open("config.json", "r") as f:
    config = json.load(f)
    GMT_timezone = config["GMT_timezone"]
    coinmarketcap_api_key = config["coinmarketcap_api_key"]
    limit = config["limit"]
    log_file = config["log_file"]
    risk = config["risk"]
    risk_safty_factor = config["risk_safty_factor"]
    binance_api_key = config["binance_api_key"]
    binance_api_secret = config["binance_api_secret"]

log(log_file, config)

client = binance.Client(binance_api_key, binance_api_secret)
pair_precision = get_precision(client)

positions, psymbol = get_openning_position(client)
log(log_file, 'Start')
show_balance(client)
show_position(positions)
log(log_file, "Summary:", get_summary(positions))
coins = get_top_coins(coinmarketcap_api_key)
symbols = get_binance_symbol()
trade_coins = set(get_trade_coins(coins, symbols, limit, only_symbol=True)).union(set(psymbol))
log(log_file, "Top Coins:\n", trade_coins)
csl_res = clear_sl(client, psymbol)
if len(csl_res) > 0:
    show_balance(client)
    show_position(positions)
print("psymbol:", psymbol)

is_refresh = False
while True:
    now = datetime.datetime.now()
    h = int(now.strftime("%H"))
    s = int(now.strftime("%S"))
    if h == GMT_timezone and s == 15 and not is_refresh:
        positions, psymbol = get_openning_position(client)
        coins = get_top_coins(coinmarketcap_api_key)
        symbols = get_binance_symbol()
        trade_coins = set(get_trade_coins(coins, symbols, limit, only_symbol=True)).union(set(psymbol))
        actions = get_actions(trade_coins)
        log(log_file, 'Action:', actions)
        is_refresh = True
        
        show_balance(client)
        show_position(positions)
        for action in actions:
            log(log_file, "action res:\n", execute_action(client, action, risk, risk_safty_factor, pair_precision, psymbol))
        positions, psymbol = get_openning_position(client)
        csl_res = clear_sl(client, psymbol)
        positions, psymbol = get_openning_position(client)
        if len(actions) > 0 or len(csl_res) > 0:
            show_balance(client)
            show_position(positions)
        log(log_file, "Summary:", get_summary(positions))
        print("psymbol:", psymbol)
    elif h == (GMT_timezone+1)%24:
        is_refresh = False
    time.sleep(1)