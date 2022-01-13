# CDCActionZone_topCoin_bot
Bull market trend Trading Bot with CDC Action Zone Indicator
<h2>Introduction</h2>
<p> CDC Action Zone is simple technical indicator from https://www.chaloke.com/forums/topic/cdc-action-zone-basic-default/ which is avalable in many platform such as TradingView
This indicator is using fast (shorter period) and slow (longer period) moving average exponential which the buy and sell signal can catchup strong uptrend and reject strong downtrend very well but not work well on sideway market. from the backtesting by using TradingView Pine script test with many crypto currency trade pair.
the result show the winrate is 30% to 40% and profit factor is 5 to 10 in each pair which is great. So, I will use this indicator to built a trading bot which will survive in bear market and can make profit in bullish trend market which will trade top 20 coins in Coinmarketcap top chart and can adjust and control risk per trade in USDT by usning position sizing. </p>
<h2>Methodology</h2>
<p> First, fetch top coins from Coinmarketcap API and get top 20 coins to be trade pairs.</p>
<p> Then, fetch historical price data from Binance API of each pair </p>
<p> Then, use historical price to calculate CDC Action Zone and get buy and sell signal of each pair. </p>
<p> If there are some buy signal find swing low of lastest 26 bars for stop loss price and use current price as entry price. Then, calculate position size by calculat size ratio which is position size in unit of coins per 1 USDT risk = 1 / (current price - stop loss) then calculate position size = size ratio * risk per trade in USDT. Then, send API request to Binance to create market order and create stop loss order. </p>
<p> If there are some sell signal get position size from Binance and create market sell order to close position. </p>
<h2>How to set config</h2>
<p> GMT_timezone: GMT timezone of your computer </p>
<p> coinmarketcap_api_key: api key which can get at https://coinmarketcap.com/api/ </p>
<p> limit: number of top coins use for trade </p>
<p> log_file: name of text file that use to store log </p>
<p> risk: risk per trade in USDT </p>
<p> risk_safety_factor: safety factor use to calculate leverage of each trade. higher safety factor will lower the leverage which will lower the risk to unexpected liquidation and use higher cost to open position </p>
<p> binance_api_key: api key of Binance account </p>
<p> binance_api_secret: api secret of Binance account </p>
