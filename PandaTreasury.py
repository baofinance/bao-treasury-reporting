#============================================================================================
# Panda Treasury Script collecting Assets values from assets and LP tokens in the treasury  =
# address. It takes a csv file as an input to browse all the ERC20 token addresses          =
# in order to check the balance of those tokens in the wallet. The output gives the value   =
# of each asset in a CSV file for reporting                                                 =
#============================================================================================
#   Date        |   Author      |   Description                                             =
# 2021.09.30    |   Baowolf     |   Initial creation of the script                          =
#============================================================================================
import web3;
import csv;
import numpy as np
from web3.types import ABI;
from decimal import Decimal
from pycoingecko import CoinGeckoAPI
import pandas as pd
import io
import os
import time

cg = CoinGeckoAPI()

Treasury = '0x8f5d46FCADEcA93356B70F40858219bB1FBf6088'
ContractOwner = '0x3bC3c8aF8CFe3dFC9bA1A57c7C3b653e3f6d6951'
CommFund = '0x609991ca0Ae39BC4EAF2669976237296D40C2F31'

#Getting price for base pairs. Accounting stables pairs worth 1$

#PNDA, BAMBOO and RHINO aren't on CG as of now. Hardcoding values on every run...

PNDAPrice = 0.000352839

BAMBOOPrice = 0.000456503

RHINOPrice = 0.000484835

BNBPrice = cg.get_price(ids='binancecoin', vs_currencies='usd')["binancecoin"]["usd"]
print("Bitcoin Price " + str(BNBPrice))

ETHPrice = cg.get_price(ids='ethereum', vs_currencies='usd')["ethereum"]["usd"]
print("Ethereum Price " + str(ETHPrice))

from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org'))

#return the path where this script is running. CSV files should be in the same directory
def file_path(relative_path):
    dir = os.path.dirname(os.path.abspath(__file__))
    split_path = relative_path.split("/")
    new_path = os.path.join(dir, *split_path)
    return new_path

#LiquidityAssetAmount look for an ERC20 balance in a wallet and if there are some, get the price from GC and calculate the amount
def liquidity_asset_amount(row, treasuryAddress, Origin) :
    #Get the token id from Coin Gecko
    tokenId = row["Token2"]
    
    #Get Balance
    contract = w3.eth.contract(Web3.toChecksumAddress(row["ContractAddress"]), abi=row["ABI"])

    #raw_balance = contract.functions.balanceOf(Treasury).call()
    Asset_balance = contract.functions.balanceOf(treasuryAddress).call()
    Asset_balance = w3.fromWei(Asset_balance, 'ether')
    
    if(Asset_balance > 0) :
        #Get CG price and parse it
        if (row["Token1"] == 'PNDA') :
            AssetPrice = PNDAPrice
        elif (row["Token1"] == 'BAMBOO') :
            AssetPrice = BAMBOOPrice
        elif (row["Token1"] == 'RHINO') :
            AssetPrice = RHINOPrice
        else :
            #Sleep a few seconds to not run into Error 429 from the Coin Geck API
            time.sleep(1)

            AssetPrice = cg.get_price(ids=tokenId, vs_currencies='usd')
            AssetPricekey = list(AssetPrice)
            try :
                AssetPrice = AssetPrice[AssetPricekey[0]]["usd"]
            except :
                AssetPrice = 0

        #Log and write to file    
        print("Number of Token of " + row["Description"] + " : " + str(Asset_balance) + " for a total value of " + str(Asset_balance * Decimal(AssetPrice)) + "$")
        write_to_treasuryFiles(row["Chain"], row["Swap"], row["Description"], row["Token1"], Asset_balance, Asset_balance * Decimal(AssetPrice), Origin)

#LiquidityPoolAmount calculate the value of each underlying assets of an LP token in a wallet
def liquidity_pool_amount(row, treasuryAddress, origin) :
    token1 = ""

    contract = w3.eth.contract(Web3.toChecksumAddress(row["ContractAddress"]), abi=row["ABI"])

    raw_balance = contract.functions.balanceOf(treasuryAddress).call()

    reserves = contract.functions.getReserves().call()
    totalCircSupply = contract.functions.totalSupply().call()

    if(raw_balance > 0):
        #Trying to find first if ETH is part of the pair, or a stable coin
        if row["Token2"] == 'ETH' :
            PriceLP = (reserves[1] / 1e18) * ETHPrice
        elif row["Token1"] == 'ETH' :
            PriceLP = (reserves[0] / 1e18) * ETHPrice
        elif row["Token1"] == 'USDC' or row["Token1"] == 'USDT' or row["Token1"] == 'DAI' or row["Token1"] == 'BUSD' :
            PriceLP = (reserves[0] / 1e18)
        elif row["Token2"] == 'USDC' or row["Token2"] == 'USDT' or row["Token2"] == 'DAI' or row["Token2"] == 'BUSD' :
            PriceLP = (reserves[1] / 1e18)
        elif row["Token2"] == 'BNB' :
            PriceLP = (reserves[1] / 1e18) * BNBPrice
        elif row["Token1"] == 'BNB' :
            PriceLP = (reserves[0] / 1e18) * BNBPrice
        else : 
            PriceLP = 0

        LP_Amount = w3.fromWei(raw_balance, 'ether')
        totalCircSupply = w3.fromWei(totalCircSupply, 'ether')
        LP_Value = (LP_Amount / totalCircSupply) * Decimal(PriceLP)
        Ratio = (LP_Amount / totalCircSupply)

        print("Number of LP of " + row["Description"] + " : " + str(LP_Amount) + " for a total value of " + str(LP_Value*2) + "$")
        write_to_treasuryFiles(row["Chain"], row["Swap"], row["Description"], row["Token1"], (reserves[0] * Ratio) / Decimal(1e18), LP_Value, origin)
        write_to_treasuryFiles(row["Chain"], row["Swap"], row["Description"], row["Token2"], (reserves[1] * Ratio) / Decimal(1e18), LP_Value, origin)

# 
def write_to_treasuryFiles (Chain, Type, From, Token, Amount, Value, Origin) :
    writer.writerow({'Chain': Chain, 'Wallet' : Origin, 'Type': Type, 'From': From, 'Token': Token, 'Amount': Amount, 'Value': Value})


#ETH Amount in wallet
BNBAmount = w3.fromWei(w3.eth.get_balance(Treasury), 'ether')
BNBAmount += w3.fromWei(w3.eth.get_balance(ContractOwner), 'ether')
print('ETH in wallet = ' + str(BNBAmount) + ' @' + str(BNBPrice) + '$ = ' + str(BNBAmount * Decimal(BNBPrice)))

#Create a reporting file to write results
with open(file_path('PandaTreasuryFunds.csv'), mode='w') as treasury_file:
    fieldnames = ['Chain', 'Wallet', 'Type', 'From', 'Token', 'Amount', 'Value']
    writer = csv.DictWriter(treasury_file, fieldnames=fieldnames, delimiter='|', lineterminator='\n')
    writer.writeheader()

    #Write ETH amount
    write_to_treasuryFiles('BNB', 'TOKEN', 'BNB', 'BNB', BNBAmount, BNBAmount * Decimal(BNBPrice), 'Fees collected')

    #Open Treasury file address to loop
    with open(file_path('PandaTreasuryContract.csv'), mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            if row["Swap"] != "TOKEN" :
                liquidity_pool_amount(row, Treasury, 'Fees collected')
                liquidity_pool_amount(row, ContractOwner, 'Contract Owner')
            else :
                liquidity_asset_amount(row, Treasury, 'Fees collected')
                liquidity_asset_amount(row, ContractOwner, 'Contract Owner')
                liquidity_asset_amount(row, CommFund, 'Community Fund')


