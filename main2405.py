import pyupbit
import time, datetime
import math, traceback
import requests
import pandas as pd
# from slack_bot import slack #NameError: name 'requests' is not defined
from tabulate import tabulate

pd.set_option('display.float_format', lambda x: f'{x:,.2f}') 

class autoTrade :
    def __init__(self, start_cash, ticker) :
        self.fee_rate = 0.0005 # 수수료 0.05%
        self.target_price = 0 # 목표 매수가
        # self.bull = False # 상승장 여부
        self.ma5 = 0 # 5일 이동평균
        self.ticker = ticker # 티커
        self.balance = upbit.get_balance(self.ticker) #매도 예약 시에도 보유수량이 0으로 초기화 되지 않는 오류가 있음
        
        self.start_cash = start_cash # 시작 자산

        self.timer = 0
        self.get_today_data()
        

    def start(self) :
        now = datetime.datetime.now() # 현재 시간

        slackBot.message("프로그램 시작 시간 : " 
                         + str(now.strftime('%m/%d - %H:%M:%S')) 
                         + "\n매매 대상 : " + self.ticker 
                         + "\n시작 원화 자산 : " + str(f"{self.start_cash:,.0f} 원")
                         + "\n보유 평단 : " + str(f"{upbit.get_avg_buy_price(self.ticker):,.0f} 원")
                         + "\t보유 수량 : " + str(f"{self.balance:,.4f}"),
                         )
        
        openTime = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1, hours=9, seconds=10) # 09:00:10

        while True :
            try :
                now = datetime.datetime.now()
                current_price = pyupbit.get_current_price(self.ticker)
                avg_buy_price = upbit.get_avg_buy_price(self.ticker) #평단 조회
                balance = upbit.get_balance(self.ticker) # 매도 예약시 보유수량 0 반영을 위한 수량 초기화

                # 구동 메세지 출력
                if(self.timer % 60 == 0) :
                    print(now.strftime('%m/%d - %H:%M:%S'),
                          "\t매도예정 :", openTime.strftime('%m/%d - %H:%M:%S'), 
                          "\t목표가 :", f"{self.target_price:,.0f}", 
                          "\t현재가 :", f"{current_price:,.0f}",
                          "\t평단 :", f"{avg_buy_price:,.0f}",
                          "\t보유수량 :", f"{balance:,.4f}",
                          "\t수익률 :", f"{(current_price*(1-self.fee_rate) - avg_buy_price) / avg_buy_price:.2%}" ,
                          "\t수익금 :", f"{(current_price*(1-self.fee_rate) - avg_buy_price ) * balance :,.0f}" ,
                          "\tMA(5) :", f"{self.ma5:,.0f}",
                          )
                
                # 매일 오전 9시 10초에 매도
                if openTime < now < openTime + datetime.timedelta(seconds=5) :
                    openTime = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1, hours=9, seconds=10)
                    if balance > 0 :# 해당 코인을 보유하고 있을 경우
                        print("==================== [ 매도 시도 ] ====================")
                        slackBot.message("매도 시도")
                        self.sell_coin()
                    self.get_today_data() # 데이터 갱신
                
                # 현재 가격이 목표가 이상이고, 5일 이동평균 이상이면서, 보유수량이 없으면 매수
                if( (current_price >= self.target_price) and (current_price >= self.ma5) and (balance==0) ) : # 매수 시도
                    print("==================== [ 매수 시도 ] ====================")
                    slackBot.message("매수 시도")
                    self.buy_coin()

                # 현재 가격이 수수료 포함 평단의 5% 이상이면 매도
                # if((current_price > (avg_buy_price/(1-self.fee_rate))*(1.05)) and self.buy_yn) : 
                #     print("==================== [ 매도 시도 ] ====================")
                #     slackBot.message("매도 시도")
                #     self.sell_coin()

                
            except Exception as err:
                slackBot.message("!!! 프로그램 오류 발생 !!!")
                slackBot.message(err)
                traceback.print_exc()
         
            self.timer += 1
            time.sleep(1)

    def get_today_data(self) :
        print("\n==================== [ 데이터 갱신 시도 ] ====================")
        daily_data = pyupbit.get_ohlcv(self.ticker, count=41)
        # 노이즈 계산 ( 1- 절대값(시가 - 종가) / (고가 - 저가) )
        daily_data['noise'] = 1 - abs(daily_data['open'] - daily_data['close']) / (daily_data['high'] - daily_data['low'])
        # 노이즈 20일 평균
        daily_data['noise_ma20'] = daily_data['noise'].rolling(window=20).mean().shift(1)
       
        # 변동폭 ( 고가 - 저가 )
        daily_data['range'] = daily_data['high'] - daily_data['low']
        # 목표매수가 ( 시가 + 변동폭 * K )
        daily_data['targetPrice'] = daily_data['open'] + daily_data['range'].shift(1) * daily_data['noise_ma20']

        # 5일 이동평균선
        daily_data['ma5'] = daily_data['close'].rolling(window=5, min_periods=1).mean().shift(1)
        # 상승장 여부
        # daily_data['bull'] = daily_data['open'] > daily_data['ma5']

        today = daily_data.iloc[-1]

        self.target_price = today.targetPrice
        # self.bull = today.bull
        self.ma5 = today.ma5
        print(tabulate(daily_data.tail(), headers = ['날짜','시작','최고','최저','마감','거래횟수','거래금액','Noise','Noise_ma20','range','목표가','MA5'], floatfmt=",.2f"))
        print("==================== [ 데이터 갱신 완료 ] ====================\n")

    def buy_coin(self) :
        balance = upbit.get_balance() # 원화 잔고 조회
        
        if balance > 5000 : # 잔고 5000원 이상일 때
            upbit.buy_market_order(self.ticker, balance * 0.9995)

            buy_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['ask_price'] # 최우선 매도 호가
            print('====================매수 시도====================')
            slackBot.message("#매수 주문\n매수 주문 가격 : " + str(buy_price) + "원")

    def sell_coin(self) :
        balance = upbit.get_balance(self.ticker) # 코인 수량 조회

        upbit.sell_market_order(ticker, balance)

        sell_price = pyupbit.get_orderbook(self.ticker)['orderbook_units'][0]['bid_price'] # 최우선 매수 호가
        print('====================매도 시도====================')
        slackBot.message("#매도 주문\n매도 주문 가격 : " + str(sell_price) + "원")

class slack :
    def __init__(self, token, channel) :
        self.token = token
        self.channel = channel

    def message(self, message):
        response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer " + self.token},
        data={"channel": self.channel,"text": message}
    )

with open("key_info.txt") as f :
    lines = f.readlines()
    acc_key = lines[0].strip()    # Access Key
    sec_key = lines[1].strip()    # Secret Key
    app_token = lines[2].strip()  # App Token
    channel = lines[3].strip()    # Slack Channel Name

upbit = pyupbit.Upbit(acc_key, sec_key)
slackBot = slack(app_token, channel)

# pyupbit login check
if upbit.get_balance() == None:
    print("check the connection")
else:
    start_cash = upbit.get_balance()
    ticker = "KRW-ETH"
    tradingBot = autoTrade(start_cash, ticker)
    tradingBot.start()

"""
거래 내역과 수익률 기록
 - 시각화
 - 엑셀
"""