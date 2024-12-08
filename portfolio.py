import asyncio
import aiohttp
import base58
from solana.rpc.async_api import AsyncClient
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token import _layouts
from solana.rpc.types import TokenAccountOpts
from solders.pubkey import Pubkey  # type: ignore
from token_info import get_token_metadata, fetch_mint_decimals  # Import the metadata function

ACCOUNT_LAYOUT = _layouts.ACCOUNT_LAYOUT


async def get_price_data(ids: list):
    """
    Asynchronously fetches price data from the Jupiter API.
    Returns a dictionary where the key is the mint address and value is the price.
    """
    ids_str = ",".join(ids)
    url = f"https://api.jup.ag/price/v2?ids={ids_str}"
    
    prices = {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    data = result.get("data", {})
                    for mint, price_data in data.items():
                        if price_data:
                            prices[mint] = price_data.get('price', 0)
                else:
                    print(f"Error: Received status code {response.status}")
                    return None
    except aiohttp.ClientError as e:
        print(f"Error::get_price_data: {e}")
        return None

    return prices


async def fetch_metadata_for_mint(mint_address, client):
    try:
        """Helper function to fetch and log metadata for a single mint address."""
        metadata = await get_token_metadata(Pubkey.from_string(mint_address), client)
        decimals = await fetch_mint_decimals(mint_address, client)  # Fetch decimals here
        if metadata:
            return {
                "mint_address": mint_address,
                "name": metadata['name'],
                "symbol": metadata['symbol'],
                "uri": metadata['uri'],
                "decimals": decimals  # Include decimals in the return
            }
        
        token_slice = mint_address[:5] + '...' + mint_address[-4:]
        return {
                "mint_address": mint_address,
                "name": None,
                "symbol": token_slice,
                "uri": None,
                "decimals": decimals  # Include decimals in the return
            }
    except Exception as error:
        print("Error::fetch_metadata_for_mint:", error)
        return None


async def user_portfolio(address):
    try:
        public_key = Pubkey.from_string(address)
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            opts = TokenAccountOpts(program_id=TOKEN_PROGRAM_ID)
            token_accounts_response = await client.get_token_accounts_by_owner(public_key, opts)
            token_accounts = token_accounts_response.value

            mint_data_list = []
            for token_account in token_accounts:
                account_data = token_account.account.data  # Base64 encoded data
                account_info = ACCOUNT_LAYOUT.parse(account_data)

                mint_address = base58.b58encode(account_info.mint).decode('utf-8')
                amount = account_info.amount  # Raw amount (in smallest unit)
                mint_data_list.append((mint_address, amount))

            # Extract just the mint addresses (first element of each tuple)
            stage_mints_for_prices = [mint for mint, _ in mint_data_list]
            
            # Fetch price data concurrently for all mints
            prices = await get_price_data(stage_mints_for_prices)

            # Fetch metadata concurrently for each mint address
            metadata_list = await asyncio.gather(
                *[fetch_metadata_for_mint(mint, client) for mint, _ in mint_data_list]
            )

            text = f"*TOKENS IN YOUR WALLET*\n\n"
            total = 0

            # Log the results, including prices if available
            for (mint_address, amount), metadata in zip(mint_data_list, metadata_list):
                if metadata:  # If metadata was fetched successfully
                    token = metadata['mint_address']
                    name = metadata['name']
                    symbol = metadata['symbol']
                    decimals = metadata['decimals']  # Get the decimals for this token
                    human_readable_amount = amount / (10 ** decimals)  # Calculate the amount correctly
                    
                    # Get price from the fetched prices (if available)
                    price = prices.get(mint_address, 0)

                    # Format the price if it's available
                    token_amount_value = float(price) * human_readable_amount
                    price_text = f"{token_amount_value:,.3}" if token_amount_value > 1 else f"{token_amount_value:,.5}"

                    total += token_amount_value

                    text += f"[{symbol}](https://solscan.io/token/{token}) {human_readable_amount:,.3f} - *(${price_text})*\n"

            text += f"\n*TOTAL BALANCE: ${total:,.3}*"
            return text
        
    except Exception as error:
        print("Error::portfolio:", error)
        return None