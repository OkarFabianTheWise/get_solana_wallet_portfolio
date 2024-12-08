#  token_info.py
import asyncio, base58
from solders.pubkey import Pubkey
from construct import Struct, Int32ul, Byte, Bytes
from spl.token._layouts import MINT_LAYOUT 

# Constants
TOKEN_METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")  # Metaplex Metadata Program ID

# Define the metadata layout based on the Metaplex standard, using Bytes instead of PaddedString
METADATA_LAYOUT = Struct(
    "key" / Int32ul,
    "update_authority" / Bytes(32),
    "mint" / Bytes(32),
    "name" / Bytes(32),  # Updated to Bytes for manual decoding
    "symbol" / Bytes(11),  # Updated to Bytes for manual decoding
    "uri" / Bytes(200),  # Updated to Bytes for manual decoding
    "seller_fee_basis_points" / Int32ul,
    "primary_sale_happened" / Byte,
    "is_mutable" / Byte
)

# Function to get the token metadata address
def get_metadata_pda(mint_address):
    return Pubkey.find_program_address(
        [
            b"metadata",
            bytes(TOKEN_METADATA_PROGRAM_ID),
            bytes(mint_address),
        ],
        TOKEN_METADATA_PROGRAM_ID,
    )[0]

# Async function to fetch and parse token metadata
async def get_token_metadata(mint_address, client):
    try:
        metadata_address = get_metadata_pda(mint_address)
        response = await client.get_account_info(metadata_address)

        if response.value is None:
            # print(f"No metadata found for mint address: {mint_address}")
            return None
         
        # print(mint_info)

        # Parse metadata using the defined layout
        account_info = METADATA_LAYOUT.parse(response.value.data)
        
        # Manually decode the name, symbol, and uri fields
        name = account_info.name.rstrip(b'\x00').decode('utf-8', errors='ignore').strip()

        symbol = account_info.symbol.rstrip(b'\x00').decode('utf-8', errors='ignore').strip()
        uri = account_info.uri.rstrip(b'\x00').decode('utf-8', errors='ignore').strip()

        return {
            "name": name,
            "symbol": symbol,
            "uri": uri
        }

    except Exception as error:
        print(f"Error fetching metadata for {mint_address}: {error}")
        return None

async def fetch_mint_decimals(mint_address, client):
    """Fetches the decimals for a given mint address with validation."""
    response = await client.get_account_info(Pubkey.from_string(mint_address))
    if response.value is None:
        print(f"No mint account found for mint address: {mint_address}")
        return 9

    # Decode and parse the mint data
    mint_data = response.value.data
    mint_info = MINT_LAYOUT.parse(mint_data)

    # Validate the decimals field to ensure it falls within a realistic range
    decimals = mint_info.decimals
    if 0 <= decimals <= 18:  # Most tokens use 0-18 decimals
        return decimals
    else:
        return 9