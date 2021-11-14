#============================================================================================
# Polly Treasury Script collecting Assets values from assets and LP tokens in the treasury  =
# address. It takes a csv file as an input to browse all the ERC20 token addresses          =
# in order to check the balance of those tokens in the wallet. The output gives the value   =
# of each asset in a CSV file for reporting                                                 =
#============================================================================================
#   Date        |   Author      |   Description                                             =
# 2021.10.02    |   Baowolf     |   Initial creation of the script                          =
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

Treasury = '0xd49aAB321F6F9A3680a0939C4D771d64b1be2f2d'
ContractOwner = '0xB1768CDdd3e6Be96B69C79FE2C3075153425D9D2'
CommFund = '0x02932f0E36EF17Eb13d77c2173CbBc09da1F1D12'
Multisig = '0x04C1279F1121713e0267fc698Dc9AF9d299C51CB'

#Getting price for base pairs. Accounting stables pairs worth 1$

RAIPrice = cg.get_price(ids='rai', vs_currencies='usd')["rai"]["usd"]
print("RAI Price " + str(RAIPrice))

ETHPrice = cg.get_price(ids='ethereum', vs_currencies='usd')["ethereum"]["usd"]
print("Ethereum Price " + str(ETHPrice))

NDEFIPrice = cg.get_price(ids='polly-defi-nest', vs_currencies='usd')["polly-defi-nest"]["usd"]
print("NDEFI Price " + str(NDEFIPrice))

MATICPrice = cg.get_price(ids='matic-network', vs_currencies='usd')["matic-network"]["usd"]
print("MATIC Price " + str(MATICPrice))

from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com'))

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
        elif row["Token2"] == 'RAI' :
            PriceLP = (reserves[1] / 1e18) * RAIPrice
        elif row["Token1"] == 'RAI' :
            PriceLP = (reserves[0] / 1e18) * RAIPrice
        elif row["Token2"] == 'NDEFI' :
            PriceLP = (reserves[1] / 1e18) * NDEFIPrice
        elif row["Token1"] == 'NDEFI' :
            PriceLP = (reserves[0] / 1e18) * NDEFIPrice
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
MATICAmount = w3.fromWei(w3.eth.get_balance(Treasury), 'ether')
MATICAmount += w3.fromWei(w3.eth.get_balance(ContractOwner), 'ether')
MATICAmount += w3.fromWei(w3.eth.get_balance(Multisig), 'ether')
print('MATIC in wallet = ' + str(MATICAmount) + ' @' + str(MATICPrice) + '$ = ' + str(MATICAmount * Decimal(MATICPrice)))

#Create a reporting file to write results
with open(file_path('PollyTreasuryFunds.csv'), mode='w') as treasury_file:
    fieldnames = ['Chain', 'Wallet', 'Type', 'From', 'Token', 'Amount', 'Value']
    writer = csv.DictWriter(treasury_file, fieldnames=fieldnames, delimiter='|', lineterminator='\n')
    writer.writeheader()

    #Write ETH amount
    write_to_treasuryFiles('MATIC', 'TOKEN', 'MATIC', 'MATIC', MATICAmount, MATICAmount * Decimal(MATICPrice), 'Fees collected')

    #Open Treasury file address to loop
    with open(file_path('PollyTreasuryContract.csv'), mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        for row in csv_reader:
            if row["Swap"] != "TOKEN" :
                liquidity_pool_amount(row, Treasury, 'Fees collected')
                liquidity_pool_amount(row, ContractOwner, 'Contract Owner')
                liquidity_pool_amount(row, Multisig, 'Contract Owner')
            else :
                liquidity_asset_amount(row, Treasury, 'Fees collected')
                liquidity_asset_amount(row, ContractOwner, 'Contract Owner')
                liquidity_asset_amount(row, CommFund, 'Community Fund')
                liquidity_asset_amount(row, Multisig, 'Community Fund')


