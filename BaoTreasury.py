#============================================================================================
# Bao Treasury Script collecting Assets values from assets and LP tokens in the treasury    =
# address. It takes a csv file as an input to browse all the ERC20 token addresses          =
# in order to check the balance of those tokens in the wallet. The output gives the value   =
# of each asset in a CSV file for reporting                                                 =
#============================================================================================
#   Date        |   Author      |   Description                                             =
# 2021.07.24    |   Baowolf     |   Initial creation of the script                          =
# 2021.08.05    |   Baowolf     |   Improvements after code review by Jon                   =
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

cg = CoinGeckoAPI()

Treasury = '0x8f5d46FCADEcA93356B70F40858219bB1FBf6088'
ContractOwner = '0x3bC3c8aF8CFe3dFC9bA1A57c7C3b653e3f6d6951'
CommFund = '0x609991ca0Ae39BC4EAF2669976237296D40C2F31'

#Getting price for base pairs. Accounting stables pairs worth 1$

BAOPrice = cg.get_price(ids='bao-finance', vs_currencies='usd')["bao-finance"]["usd"]
print("Bao Price " + str(BAOPrice))

BTCPrice = cg.get_price(ids='bitcoin', vs_currencies='usd')["bitcoin"]["usd"]
print("Bitcoin Price " + str(BTCPrice))

ETHPrice = cg.get_price(ids='ethereum', vs_currencies='usd')["ethereum"]["usd"]
print("Ethereum Price " + str(ETHPrice))

SushiPrice = cg.get_price(ids='sushi', vs_currencies='usd')["sushi"]["usd"]
print("Sushi Price " + str(SushiPrice))

from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/601e4691fe3a4f6b9b83fe65e487190d'))
w3xDai = Web3(Web3.HTTPProvider('https://rpc.xdaichain.com'))

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
    if (row["Chain"] == "xDAI"):
        contract = w3xDai.eth.contract(Web3.toChecksumAddress(row["ContractAddress"]), abi=row["ABI"])
    else:
        contract = w3.eth.contract(row["ContractAddress"], abi=row["ABI"])

    #raw_balance = contract.functions.balanceOf(Treasury).call()
    Asset_balance = contract.functions.balanceOf(treasuryAddress).call()
    Asset_balance = w3.fromWei(Asset_balance, 'ether')
    
    if(Asset_balance > 0) :
        #Get CG price and parse it
        AssetPrice = cg.get_price(ids=tokenId, vs_currencies='usd')
        AssetPricekey = list(AssetPrice)
        AssetPrice = AssetPrice[AssetPricekey[0]]["usd"]

        #Log and write to file    
        print("Number of Token of " + row["Description"] + " : " + str(Asset_balance) + " for a total value of " + str(Asset_balance * Decimal(AssetPrice)) + "$")
        write_to_treasuryFiles(row["Chain"], row["Swap"], row["Description"], row["Token1"], Asset_balance, Asset_balance * Decimal(AssetPrice), Origin)

#LiquidityPoolAmount calculate the value of each underlying assets of an LP token in a wallet
def liquidity_pool_amount(row, treasuryAddress, origin) :
    token1 = ""

    if (row["Chain"] == "xDAI"):
        contract = w3xDai.eth.contract(Web3.toChecksumAddress(row["ContractAddress"]), abi=row["ABI"])
        if(row["Swap"] != "SUSHI"):
            token0 = contract.functions.token0().call()
            token1 = contract.functions.token1().call()     
    else:
        contract = w3.eth.contract(row["ContractAddress"], abi=row["ABI"])

    raw_balance = contract.functions.balanceOf(treasuryAddress).call()

    #If we have SLP Tokens on xDai, we get the balances of the token on xDai, then interact with the contract on ETH
    if(row["Swap"] == "SUSHI" and row["Chain"] == "xDAI"):
        contract = w3.eth.contract(Web3.toChecksumAddress(row["ETHContractAddress"]), abi=row["ABI"])
        token1 = contract.functions.token1().call()  

    reserves = contract.functions.getReserves().call()
    totalCircSupply = contract.functions.totalSupply().call()

    if(raw_balance > 0):
        #Trying to find first if ETH is part of the pair, or a stable coin
        if row["Token2"] == 'ETH' :
            PriceLP = (reserves[1] / 1e18) * ETHPrice
        elif row["Token1"] == 'ETH' :
            PriceLP = (reserves[0] / 1e18) * ETHPrice
        elif row["Token1"] == 'USDC' or row["Token1"] == 'USDT' or row["Token1"] == 'DAI' or row["Token1"] == 'xDAI' :
            PriceLP = (reserves[0] / 1e18)
        elif row["Token2"] == 'USDC' or row["Token2"] == 'USDT' or row["Token2"] == 'DAI' or row["Token2"] == 'xDAI' :
            PriceLP = (reserves[1] / 1e18)
        elif row["Token1"] == 'BAO' :
            PriceLP = (reserves[0] / 1e18) * BAOPrice
        elif row["Token2"] == 'BAO' :
            PriceLP = (reserves[1] / 1e18) * BAOPrice
        elif row["Token1"] == 'SUSHI' :
            PriceLP = Decimal(reserves[0] / 1e18) * Decimal(SushiPrice)
        elif row["Token2"] == 'SUSHI' :
            PriceLP = Decimal(reserves[1] / 1e18) * Decimal(SushiPrice)
        elif row["Token1"] == 'wBTC' :
            PriceLP = Decimal(reserves[0] / 1e18) * BTCPrice
        elif row["Token2"] == 'wBTC' :
            PriceLP = Decimal(reserves[1] / 1e18) * BTCPrice
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
EthAmount = w3.fromWei(w3.eth.get_balance(Treasury), 'ether')
EthAmount += w3.fromWei(w3.eth.get_balance(ContractOwner), 'ether')
print('ETH in wallet = ' + str(EthAmount) + ' @' + str(ETHPrice) + '$ = ' + str(EthAmount * Decimal(ETHPrice)))

xDaiAmount = w3xDai.fromWei(w3xDai.eth.get_balance(Treasury), 'ether')
xDaiAmount += w3xDai.fromWei(w3xDai.eth.get_balance(ContractOwner), 'ether')
print('xDai in wallet = ' + str(xDaiAmount) + ' @' + str(1) + '$ = ' + str(xDaiAmount * Decimal(1)))

#Create a reporting file to write results
with open(file_path('TreasuryFunds.csv'), mode='w') as treasury_file:
    fieldnames = ['Chain', 'Wallet', 'Type', 'From', 'Token', 'Amount', 'Value']
    writer = csv.DictWriter(treasury_file, fieldnames=fieldnames, delimiter='|', lineterminator='\n')
    writer.writeheader()

    #Write ETH amount
    write_to_treasuryFiles('ETH', 'TOKEN', 'Ethereum', 'ETH', EthAmount, EthAmount * Decimal(ETHPrice), 'Fees collected')

    #Write xDai amount
    write_to_treasuryFiles('xDAI', 'TOKEN', 'xDAI', 'xDAI', xDaiAmount, xDaiAmount, 'Fees collected')

    #Exclude the manual minting of Baocx on xDai
    write_to_treasuryFiles('xDAI', 'TOKEN', 'BAOcx', 'BAOcx', -888898417791, -888898417791 * BAOPrice, 'Contract Owner')

    #Open Treasury file address to loop
    with open(file_path('TreasuryContract.csv'), mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            if row["Swap"] != "TOKEN" :
                liquidity_pool_amount(row, Treasury, 'Fees collected')
                liquidity_pool_amount(row, ContractOwner, 'Contract Owner')
            else :
                liquidity_asset_amount(row, Treasury, 'Fees collected')
                liquidity_asset_amount(row, ContractOwner, 'Contract Owner')
                liquidity_asset_amount(row, CommFund, 'Community Fund')


