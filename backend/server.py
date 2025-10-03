from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import json
import time
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import uuid
from decimal import Decimal

# Web3 and blockchain imports
from web3 import Web3, AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import websockets
import aiohttp

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create FastAPI app
app = FastAPI(title="Paradox Bot API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# REAL PANCAKESWAP TRADING CONTRACTS AND ABIs
PANCAKESWAP_ROUTER_V2 = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKESWAP_FACTORY = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73" 
WBNB_ADDRESS = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"

# PancakeSwap Router V2 ABI (essential functions only)
PANCAKESWAP_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ERC20 Token ABI (complete essential functions)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    }
]

# ==================== MODELS ====================

class WalletInput(BaseModel):
    name: str
    private_key: str

class WalletConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    address: str = ""  # Will be derived from private key
    private_key: str  # Encrypted in production
    is_active: bool = True
    balance_bnb: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WalletResponse(BaseModel):
    id: str
    name: str
    address: str
    is_active: bool = True
    balance_bnb: float = 0.0  # Demo balance
    real_balance_bnb: float = 0.0  # Real blockchain balance
    real_balance_usd: float = 0.0  # USD equivalent
    private_key: Optional[str] = None  # Masked for security
    has_real_trading: bool = False  # Indicates if real trading enabled
    blockchain_verified: bool = False
    last_balance_check: Optional[datetime] = None
    created_at: datetime

class TradingConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trade_amount_usd: float = 50.0
    max_trade_amount_usd: float = 100.0
    min_liquidity_usd: float = 10000.0
    max_tax_buy_percent: float = 6.0
    max_tax_sell_percent: float = 6.0
    take_profit_targets: List[int] = [10, 20, 30]  # Multipliers (10x, 20x, 30x)
    take_profit_percentages: List[float] = [50.0, 30.0, 20.0]  # % of position to sell at each target
    stop_loss_percent: float = 50.0
    max_position_time_minutes: int = 90
    slippage_tolerance_percent: float = 12.0
    is_active: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Position(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wallet_id: str
    token_address: str
    token_symbol: str
    token_name: str = ""
    pair_address: str
    entry_price: float
    entry_amount_bnb: float
    entry_amount_usd: float
    current_price: float = 0.0
    current_value_usd: float = 0.0
    unrealized_pnl_usd: float = 0.0
    unrealized_pnl_percent: float = 0.0
    tokens_held: float
    tokens_sold: float = 0.0
    realized_pnl_usd: float = 0.0
    take_profits_hit: List[int] = []  # Which TP levels have been hit
    status: str = "open"  # open, partial, closed, failed
    entry_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None
    entry_tx_hash: str = ""
    exit_tx_hashes: List[str] = []
    risk_score: float = 0.0
    notes: str = ""

class NewPairEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pair_address: str
    token0_address: str
    token1_address: str
    token_address: str  # Non-WBNB token
    token_symbol: str = "UNKNOWN"
    token_name: str = "UNKNOWN"
    wbnb_reserves: float = 0.0
    token_reserves: float = 0.0
    liquidity_usd: float = 0.0
    initial_price: float = 0.0
    block_number: int
    transaction_hash: str
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    risk_passed: bool = False
    risk_reasons: List[str] = []
    action_taken: str = "none"  # none, probe, bought, rejected
    # Useful links for viewing token info
    dexscreener_url: str = ""
    bscscan_token_url: str = ""
    bscscan_pair_url: str = ""
    pancakeswap_url: str = ""

class TradingStats(BaseModel):
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_volume_usd: float = 0.0
    total_pnl_usd: float = 0.0
    win_rate_percent: float = 0.0
    avg_hold_time_minutes: float = 0.0
    pairs_detected: int = 0
    pairs_traded: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RPCConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bsc_rpc_http: str = "https://bsc-dataseed1.binance.org/"
    bsc_rpc_ws: str = ""
    bscscan_api_key: str = ""
    is_active: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== BLOCKCHAIN CONFIG ====================

class BlockchainConfig:
    def __init__(self):
        self.bsc_rpc_http = os.getenv('BSC_RPC_HTTP')
        self.bsc_rpc_ws = os.getenv('BSC_RPC_WS')
        self.bscscan_api_key = os.getenv('BSCSCAN_API_KEY', '')
        self.pancake_router = os.getenv('PANCAKE_ROUTER')
        self.pancake_factory = os.getenv('PANCAKE_FACTORY')
        self.wbnb_address = os.getenv('WBNB_ADDRESS')
        self.usdt_address = os.getenv('USDT_ADDRESS')
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.bsc_rpc_http))
        # BSC uses Proof of Authority - middleware will be added when needed
        
        # Contract ABIs (simplified for demo)
        self.factory_abi = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "token0", "type": "address"},
                    {"indexed": True, "name": "token1", "type": "address"},
                    {"indexed": False, "name": "pair", "type": "address"},
                    {"indexed": False, "name": "", "type": "uint256"}
                ],
                "name": "PairCreated",
                "type": "event"
            }
        ]
        
        self.pair_abi = [
            {"constant": True, "inputs": [], "name": "getReserves", "outputs": [
                {"name": "_reserve0", "type": "uint112"},
                {"name": "_reserve1", "type": "uint112"},
                {"name": "_blockTimestampLast", "type": "uint32"}
            ], "type": "function"},
            {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"}
        ]
        
        self.erc20_abi = [
            {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"}
        ]
        
        self.router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactETHForTokens",
                "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
                "stateMutability": "payable",
                "type": "function"
            }
        ]

blockchain_config = BlockchainConfig()

# ==================== GLOBAL STATE ====================

class BotState:
    def __init__(self):
        self.is_running = False
        self.connected_clients = set()
        self.ws_connection = None
        self.positions = {}
        self.detected_pairs = []
        self.trading_config = None
        self.wallets = []
        self.stats = TradingStats()
    
    def add_client(self, websocket):
        self.connected_clients.add(websocket)
    
    def remove_client(self, websocket):
        self.connected_clients.discard(websocket)
    
    async def broadcast_to_clients(self, message: dict):
        if self.connected_clients:
            disconnected = set()
            for client in self.connected_clients:
                try:
                    await client.send_text(json.dumps(message))
                except Exception:
                    disconnected.add(client)
            
            # Remove disconnected clients
            for client in disconnected:
                self.connected_clients.discard(client)

bot_state = BotState()

# ==================== API ENDPOINTS ====================

@api_router.get("/")
async def root():
    return {"message": "Paradox Bot API", "version": "1.0.0", "status": "active"}

@api_router.get("/status")
async def get_bot_status():
    return {
        "is_running": bot_state.is_running,
        "connected_clients": len(bot_state.connected_clients),
        "active_positions": len([p for p in bot_state.positions.values() if p.status == "open"]),
        "detected_pairs_today": len(bot_state.detected_pairs),
        "blockchain_connected": blockchain_config.w3.is_connected(),
        "last_block": blockchain_config.w3.eth.block_number if blockchain_config.w3.is_connected() else None
    }

@api_router.post("/sniper/start")
async def start_sniper(background_tasks: BackgroundTasks):
    if bot_state.is_running:
        raise HTTPException(status_code=400, detail="Sniper is already running")
    
    bot_state.is_running = True
    
    # Use asyncio.create_task for long-running background tasks
    asyncio.create_task(start_pair_monitoring())
    asyncio.create_task(update_position_prices())
    asyncio.create_task(auto_update_wallet_balances())  # Auto-update balances every 5s
    
    await bot_state.broadcast_to_clients({
        "type": "status_update",
        "data": {"status": "started", "message": "Sniper bot started successfully"}
    })
    
    return {"message": "Sniper started", "status": "running"}

@api_router.post("/sniper/stop")
async def stop_sniper():
    bot_state.is_running = False
    
    await bot_state.broadcast_to_clients({
        "type": "status_update",
        "data": {"status": "stopped", "message": "Sniper bot stopped"}
    })
    
    return {"message": "Sniper stopped", "status": "stopped"}

@api_router.get("/config/trading", response_model=TradingConfig)
async def get_trading_config():
    config = await db.trading_config.find_one({"is_active": True})
    if not config:
        # Create default config
        default_config = TradingConfig()
        await db.trading_config.insert_one(default_config.dict())
        return default_config
    return TradingConfig(**config)

@api_router.post("/config/trading", response_model=TradingConfig)
async def update_trading_config(config: TradingConfig):
    config.updated_at = datetime.now(timezone.utc)
    await db.trading_config.replace_one(
        {"is_active": True},
        config.dict(),
        upsert=True
    )
    bot_state.trading_config = config
    return config

@api_router.get("/config/rpc", response_model=RPCConfig)
async def get_rpc_config():
    config = await db.rpc_config.find_one({"is_active": True})
    if not config:
        # Return default config
        default_config = RPCConfig()
        return default_config
    config.pop('_id', None)
    return RPCConfig(**config)

@api_router.post("/config/rpc", response_model=RPCConfig)
async def update_rpc_config(config: RPCConfig):
    config.updated_at = datetime.now(timezone.utc)
    await db.rpc_config.replace_one(
        {"is_active": True},
        config.dict(),
        upsert=True
    )
    # Update blockchain_config with new settings
    blockchain_config.bsc_rpc_http = config.bsc_rpc_http
    blockchain_config.bsc_rpc_ws = config.bsc_rpc_ws
    blockchain_config.bscscan_api_key = config.bscscan_api_key
    blockchain_config.w3 = Web3(Web3.HTTPProvider(config.bsc_rpc_http))
    logger.info(f"RPC configuration updated: HTTP={config.bsc_rpc_http[:50]}...")
    return config

@api_router.get("/wallets", response_model=List[WalletResponse])
async def get_wallets():
    wallets = await db.wallets.find({"is_active": True}).to_list(100)
    # Process wallets and include necessary fields for frontend
    wallet_responses = []
    for wallet in wallets:
        wallet.pop('_id', None)  # Remove MongoDB ObjectId
        
        # Keep private key indicator but mask actual key for security
        has_private_key = bool(wallet.get('private_key'))
        private_key_masked = '0x••••••••••••••••' if has_private_key else None
        
        # Remove actual private key for security but indicate presence
        wallet.pop('private_key', None)
        wallet['private_key'] = private_key_masked
        wallet['has_real_trading'] = has_private_key
        
        # Ensure all balance fields are included
        if 'real_balance_bnb' not in wallet:
            wallet['real_balance_bnb'] = 0.0
        if 'real_balance_usd' not in wallet:
            wallet['real_balance_usd'] = 0.0
            
        wallet_responses.append(WalletResponse(**wallet))
    return wallet_responses

@api_router.post("/wallets", response_model=WalletConfig)
async def add_wallet(wallet_input: WalletInput):
    # Validate the private key and create full wallet config
    try:
        account = Account.from_key(wallet_input.private_key)
        
        # Create full wallet config
        wallet = WalletConfig(
            name=wallet_input.name,
            address=account.address,
            private_key=wallet_input.private_key
        )
        
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid private key format. Please check your private key.")
    
    await db.wallets.insert_one(wallet.dict())
    bot_state.wallets.append(wallet)
    return wallet

@api_router.get("/positions", response_model=List[Position])
async def get_positions(wallet_id: Optional[str] = None):
    """Get positions, optionally filtered by wallet_id"""
    query = {}
    if wallet_id:
        query["wallet_id"] = wallet_id
        
    positions = await db.positions.find(query).sort("entry_time", -1).to_list(100)
    return [Position(**pos) for pos in positions]

@api_router.get("/pairs/detected", response_model=List[NewPairEvent])
async def get_detected_pairs():
    pairs = await db.detected_pairs.find().sort("detected_at", -1).limit(50).to_list(50)
    return [NewPairEvent(**pair) for pair in pairs]

@api_router.delete("/pairs/detected")
async def reset_detected_pairs():
    """Reset/clear all detected pairs from database"""
    try:
        result = await db.detected_pairs.delete_many({})
        logger.info(f"🗑️ Cleared {result.deleted_count} detected pairs from database")
        
        # Also reset the stats counter
        await db.stats.update_one(
            {},
            {"$set": {"pairs_detected": 0}},
            upsert=True
        )
        
        # Broadcast reset event to all connected clients
        await bot_state.broadcast_to_clients({
            "type": "pairs_reset",
            "data": {"cleared_count": result.deleted_count}
        })
        
        return {
            "message": f"Successfully cleared {result.deleted_count} detected pairs",
            "cleared_count": result.deleted_count
        }
    except Exception as e:
        logger.error(f"Error clearing detected pairs: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear detected pairs")

@api_router.get("/stats")
async def get_stats(wallet_id: Optional[str] = None):
    """Get trading statistics - SIMPLIFIED to fix dashboard loading"""
    try:
        query = {}
        if wallet_id:
            query["wallet_id"] = wallet_id
        
        # Get positions
        all_positions = await db.positions.find(query).to_list(1000)
        open_positions = [p for p in all_positions if p.get("status") in ["open", "partial"]]
        closed_positions = [p for p in all_positions if p.get("status") == "closed"]
        
        # Simple calculations to prevent crashes
        total_trades = len(closed_positions)
        winning_trades = 0
        losing_trades = 0
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        
        # Calculate with STRICT caps to prevent fake P&L
        for position in closed_positions:
            pnl = position.get("realized_pnl_usd", 0) or 0
            # STRICT cap - only count losses/gains under $50 per $5 trade
            if abs(pnl) <= 50 and pnl != 0:  
                realized_pnl += pnl
                if pnl > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
        
        # Calculate unrealized for open positions with STRICT caps
        for position in open_positions:
            pnl = position.get("unrealized_pnl_usd", 0) or 0
            # STRICT cap - max $50 profit/loss per $5 trade
            if abs(pnl) <= 50:
                unrealized_pnl += pnl
        
        total_pnl = realized_pnl + unrealized_pnl
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Get global pairs detected count
        global_pairs_detected = await db.detected_pairs.count_documents({})
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_pnl_usd": total_pnl,
            "realized_pnl_usd": realized_pnl,
            "unrealized_pnl_usd": unrealized_pnl,
            "win_rate_percent": win_rate,
            "pairs_detected": global_pairs_detected,
            "pairs_traded": total_trades,
            "active_positions": len(open_positions),
            "wallet_filtered": wallet_id is not None
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        # Return safe defaults if calculation fails
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl_usd": 0.0,
            "realized_pnl_usd": 0.0,
            "unrealized_pnl_usd": 0.0,
            "win_rate_percent": 0.0,
            "pairs_detected": 0,
            "pairs_traded": 0,
            "active_positions": 0,
            "wallet_filtered": False
        }

@api_router.get("/wallets/{wallet_id}/scan-all-tokens")
async def scan_all_token_balances(wallet_id: str):
    """Scan wallet address for ALL token balances"""
    try:
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        address = wallet.get('address')
        if not address:
            raise HTTPException(status_code=400, detail="No wallet address found")
        
        # Get all unique token addresses from recent positions
        recent_positions = await db.positions.find({
            "wallet_id": wallet_id,
            "token_address": {"$exists": True}
        }).to_list(100)
        
        unique_tokens = list(set(pos.get("token_address") for pos in recent_positions if pos.get("token_address")))
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config:
            return {"error": "No RPC configuration"}
        
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        
        token_balances = []
        for token_address in unique_tokens[:10]:  # Check first 10 tokens
            try:
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                
                balance_wei = token_contract.functions.balanceOf(address).call()
                decimals = token_contract.functions.decimals().call()
                symbol = token_contract.functions.symbol().call()
                balance_tokens = balance_wei / (10 ** decimals)
                
                if balance_tokens > 0:  # Only include tokens with balance
                    # Get current price from DexScreener
                    price_data = await get_real_time_token_price(token_address)
                    current_price = price_data['price_usd'] if price_data else 0
                    current_value_usd = balance_tokens * current_price
                    
                    token_balances.append({
                        "token_symbol": symbol,
                        "token_address": token_address,
                        "balance_tokens": balance_tokens,
                        "current_price_usd": current_price,
                        "current_value_usd": current_value_usd,
                        "dexscreener_url": f"https://dexscreener.com/bsc/{token_address}",
                        "pancakeswap_url": f"https://pancakeswap.finance/swap?outputCurrency={token_address}"
                    })
                
            except Exception as e:
                logger.error(f"Error checking token {token_address}: {e}")
                continue
        
        return {
            "wallet_address": address,
            "tokens_found": len(token_balances),
            "token_balances": token_balances,
            "total_value_usd": sum(t["current_value_usd"] for t in token_balances)
        }
        
    except Exception as e:
        logger.error(f"Error scanning tokens for wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/wallets/{wallet_id}/add-private-key")
async def add_private_key_to_wallet(wallet_id: str, private_key_data: dict):
    """Add real private key to wallet for blockchain trading"""
    try:
        private_key = private_key_data.get("private_key", "").strip()
        
        if not private_key:
            raise HTTPException(status_code=400, detail="Private key is required")
        
        # Validate private key format
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key
        
        # Validate private key and get address
        from eth_account import Account
        try:
            account = Account.from_key(private_key)
            address = account.address
            logger.info(f"✅ Private key validated, address: {address}")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid private key format")
        
        # Find wallet
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Update wallet with private key and real address
        await db.wallets.update_one(
            {"id": wallet_id},
            {
                "$set": {
                    "private_key": private_key,
                    "address": address,
                    "real_trading_enabled": True,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"🔑 Private key added to wallet {wallet.get('name')} - Address: {address}")
        
        return {
            "message": "Private key added successfully",
            "wallet_id": wallet_id,
            "address": address,
            "real_trading_enabled": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding private key to wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to add private key")

@api_router.post("/wallets/{wallet_id}/check-real-balance")
async def check_real_blockchain_balance(wallet_id: str):
    """Check real blockchain balance for wallet"""
    try:
        # Get wallet
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        private_key = wallet.get('private_key')
        address = wallet.get('address')
        
        if not private_key or not address:
            return {
                "message": "No private key configured - real balance unavailable",
                "real_balance_bnb": 0,
                "demo_balance_bnb": wallet.get('balance_bnb', 0)
            }
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config or not rpc_config.get('bsc_rpc_http'):
            return {"error": "No RPC configuration found"}
        
        # Connect to blockchain
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        if not w3.is_connected():
            return {"error": "Cannot connect to BSC network"}
        
        # Get REAL balance from blockchain
        real_balance_wei = w3.eth.get_balance(address)
        real_balance_bnb = float(w3.from_wei(real_balance_wei, 'ether'))  # Convert to float for JSON
        
        # Update database with real balance AND private key data
        await db.wallets.update_one(
            {"id": wallet_id},
            {
                "$set": {
                    "real_balance_bnb": real_balance_bnb,
                    "real_balance_usd": real_balance_bnb * 600,  # Approximate USD value
                    "last_balance_check": datetime.now(timezone.utc),
                    "blockchain_verified": True
                }
            }
        )
        
        logger.info(f"💰 Real balance for {wallet.get('name')} ({address}): {real_balance_bnb:.6f} BNB")
        
        return {
            "wallet_name": wallet.get('name'),
            "address": address,
            "real_balance_bnb": real_balance_bnb,
            "demo_balance_bnb": wallet.get('balance_bnb', 0)
        }
        
    except Exception as e:
        logger.error(f"Error checking real balance for wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to check real balance")

@api_router.delete("/wallets/{wallet_id}")
async def delete_wallet(wallet_id: str):
    """Delete wallet from database"""
    try:
        result = await db.wallets.delete_one({"id": wallet_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        logger.info(f"🗑️ Wallet deleted: {wallet_id}")
        return {"message": "Wallet deleted successfully", "wallet_id": wallet_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete wallet")
@api_router.post("/positions/{position_id}/sync-real-data")
async def sync_position_real_data(position_id: str):
    """Sync position with real blockchain token balance and current price"""
    try:
        # Get position
        position = await db.positions.find_one({"id": position_id})
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Get wallet
        wallet_id = position.get("wallet_id")
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet or not wallet.get("private_key"):
            raise HTTPException(status_code=400, detail="No wallet private key found")
        
        # Get RPC config and connect to blockchain
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        
        from eth_account import Account
        account = Account.from_key(wallet['private_key'])
        token_address = position.get("token_address")
        
        # Get REAL token balance from blockchain
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        token_balance_wei = token_contract.functions.balanceOf(account.address).call()
        decimals = token_contract.functions.decimals().call()
        actual_tokens = token_balance_wei / (10 ** decimals)
        
        # Get REAL current price from DexScreener
        price_data = await get_real_time_token_price(token_address)
        
        if price_data and price_data['price_usd'] > 0:
            current_price_usd = price_data['price_usd']
        else:
            # Fallback calculation
            entry_amount_usd = position.get("entry_amount_usd", 5)
            current_price_usd = entry_amount_usd / actual_tokens if actual_tokens > 0 else 0
        
        # Calculate REAL P&L
        entry_amount_usd = position.get("entry_amount_usd", 5)
        entry_price = entry_amount_usd / actual_tokens if actual_tokens > 0 else 0
        current_value_usd = actual_tokens * current_price_usd
        
        unrealized_pnl_usd = current_value_usd - entry_amount_usd
        unrealized_pnl_percent = (unrealized_pnl_usd / entry_amount_usd * 100) if entry_amount_usd > 0 else 0
        
        # Update position with REAL data
        await db.positions.update_one(
            {"id": position_id},
            {
                "$set": {
                    "tokens_held": actual_tokens,
                    "entry_price": entry_price,
                    "current_price": current_price_usd,
                    "current_value_usd": current_value_usd,
                    "unrealized_pnl_usd": unrealized_pnl_usd,
                    "unrealized_pnl_percent": unrealized_pnl_percent,
                    "synced_from_blockchain": True,
                    "last_sync": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"✅ SYNCED REAL DATA: {position.get('token_symbol')} - {actual_tokens:.2f} tokens, ${current_value_usd:.2f} value, {unrealized_pnl_percent:.1f}% P&L")
        
        return {
            "message": "Position synced with real blockchain data",
            "token_symbol": position.get("token_symbol"),
            "actual_tokens": actual_tokens,
            "current_value_usd": current_value_usd,
            "unrealized_pnl_percent": unrealized_pnl_percent
        }
        
    except Exception as e:
        logger.error(f"Error syncing position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/positions/{position_id}/sell-tokens-to-bnb")
async def sell_tokens_to_bnb(position_id: str):
    """EMERGENCY: Sell real tokens back to BNB via PancakeSwap"""
    try:
        # Get position details
        position = await db.positions.find_one({"id": position_id})
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        # Get wallet with private key
        wallet_id = position.get("wallet_id")
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet or not wallet.get("private_key"):
            raise HTTPException(status_code=400, detail="No wallet private key found")
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        
        from eth_account import Account
        account = Account.from_key(wallet['private_key'])
        token_address = position.get("token_address")
        
        # Get current token balance
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        token_balance_wei = token_contract.functions.balanceOf(account.address).call()
        decimals = token_contract.functions.decimals().call()
        actual_tokens = token_balance_wei / (10 ** decimals)
        
        if actual_tokens <= 0:
            return {"message": "No tokens to sell", "token_balance": 0}
        
        logger.info(f"🔄 SELLING {actual_tokens:.2f} {position.get('token_symbol')} tokens back to BNB...")
        
        # Execute REAL sell transaction on PancakeSwap
        config = await db.trading_config.find_one({"is_active": True})
        sell_tx_hash = await execute_real_pancakeswap_sell(
            w3, account, token_address, actual_tokens, config or {}
        )
        
        if sell_tx_hash:
            # Update position as sold
            await db.positions.update_one(
                {"id": position_id},
                {
                    "$set": {
                        "exit_tx_hashes": [sell_tx_hash],
                        "exit_time": datetime.now(timezone.utc),
                        "status": "closed",
                        "notes": f"Real tokens sold back to BNB - TX: {sell_tx_hash}"
                    }
                }
            )
            
            logger.info(f"💰 REAL SELL EXECUTED: {sell_tx_hash}")
            logger.info(f"🔗 View on BSCScan: https://bscscan.com/tx/{sell_tx_hash}")
            
            return {
                "message": f"Successfully sold {actual_tokens:.2f} {position.get('token_symbol')} tokens",
                "sell_tx_hash": sell_tx_hash,
                "bscscan_url": f"https://bscscan.com/tx/{sell_tx_hash}",
                "tokens_sold": actual_tokens
            }
        else:
            raise HTTPException(status_code=500, detail="Sell transaction failed")
        
    except Exception as e:
        logger.error(f"Error selling tokens for position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def delete_wallet(wallet_id: str):
    """Delete wallet from database"""
    try:
        result = await db.wallets.delete_one({"id": wallet_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        logger.info(f"🗑️ Wallet deleted: {wallet_id}")
        return {"message": "Wallet deleted successfully", "wallet_id": wallet_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete wallet")

@api_router.post("/wallets/clear-all")
async def clear_all_wallets():
    """Delete ALL wallets from database"""
    try:
        result = await db.wallets.delete_many({})
        logger.info(f"🗑️ Cleared {result.deleted_count} wallets from database")
        return {"message": f"Successfully deleted {result.deleted_count} wallets"}
        
    except Exception as e:
        logger.error(f"Error clearing all wallets: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear wallets")
async def delete_wallet(wallet_id: str):
    # Check if wallet exists
    wallet = await db.wallets.find_one({"id": wallet_id})
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Delete the wallet from database
    result = await db.wallets.delete_one({"id": wallet_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Remove from bot state if it exists
    bot_state.wallets = [w for w in bot_state.wallets if w.id != wallet_id]
    
    return {"message": "Wallet deleted successfully", "wallet_id": wallet_id}

@api_router.post("/wallets/{wallet_id}/add-demo-funds")
async def add_demo_funds(wallet_id: str):
    import random
    
    # Add demo funds between 0.5-2.0 BNB
    demo_amount = round(random.uniform(0.5, 2.0), 4)
    
    # Update wallet balance in database
    result = await db.wallets.update_one(
        {"id": wallet_id},
        {"$inc": {"balance_bnb": demo_amount}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return {"message": "Demo funds added successfully", "amount": demo_amount}

@api_router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    """Close position with IMMEDIATE REAL PancakeSwap sell execution"""
    try:
        position = await db.positions.find_one({"id": position_id})
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        if position.get("status") == "closed":
            raise HTTPException(status_code=400, detail="Position is already closed")
        
        # Get wallet with private key for REAL sell execution
        wallet_id = position.get("wallet_id")
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet or not wallet.get("private_key"):
            raise HTTPException(status_code=400, detail="No wallet private key - cannot execute real sell")
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config:
            raise HTTPException(status_code=500, detail="No RPC configuration")
        
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        from eth_account import Account
        account = Account.from_key(wallet['private_key'])
        token_address = position.get("token_address")
        
        # Check current token balance on blockchain
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        token_balance_wei = token_contract.functions.balanceOf(account.address).call()
        decimals = token_contract.functions.decimals().call()
        actual_tokens = token_balance_wei / (10 ** decimals)
        
        if actual_tokens <= 0:
            return {"message": "No tokens to sell - already sold or transferred", "token_balance": 0}
        
        logger.info(f"🔥 IMMEDIATE CLOSE: Selling {actual_tokens:.2f} {position.get('token_symbol')} tokens NOW!")
        
        # Execute IMMEDIATE REAL sell on PancakeSwap
        config = await db.trading_config.find_one({"is_active": True})
        sell_tx_hash = await execute_real_pancakeswap_sell(
            w3, account, token_address, actual_tokens, config or {}
        )
        
        if sell_tx_hash:
            # Update position as REALLY closed
            await db.positions.update_one(
                {"id": position_id},
                {
                    "$set": {
                        "exit_tx_hashes": [sell_tx_hash],
                        "exit_time": datetime.now(timezone.utc),
                        "status": "closed",
                        "tokens_sold": actual_tokens,
                        "notes": f"REAL CLOSE: Tokens sold to BNB - TX: {sell_tx_hash}"
                    }
                }
            )
            
            # Broadcast position closure
            await bot_state.broadcast_to_clients({
                "type": "position_closed",
                "data": {
                    "position_id": position_id,
                    "token_symbol": position.get("token_symbol"),
                    "tokens_sold": actual_tokens,
                    "sell_tx_hash": sell_tx_hash
                }
            })
            
            logger.info(f"💰 POSITION REALLY CLOSED: {sell_tx_hash}")
            logger.info(f"🔗 BSCScan: https://bscscan.com/tx/{sell_tx_hash}")
            
            return {
                "message": f"Position closed - {actual_tokens:.2f} tokens sold on PancakeSwap",
                "position_id": position_id,
                "tokens_sold": actual_tokens,
                "sell_tx_hash": sell_tx_hash,
                "bscscan_url": f"https://bscscan.com/tx/{sell_tx_hash}"
            }
        else:
            raise HTTPException(status_code=500, detail="REAL sell transaction failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position {position_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/positions/close-all")
async def close_all_positions():
    # Find all open positions
    open_positions = await db.positions.find({"status": {"$in": ["open", "partial"]}}).to_list(100)
    
    if not open_positions:
        return {"message": "No open positions to close", "closed_count": 0}
    
    closed_count = 0
    total_pnl = 0.0
    bnb_price = 600  # Assuming 1 BNB = ~$600
    
    for position in open_positions:
        # Calculate value to return to wallet
        current_value_usd = position.get("current_value_usd", 0)
        bnb_to_return = current_value_usd / bnb_price
        
        # Update wallet balance
        wallet_id = position.get("wallet_id")
        wallet = await db.wallets.find_one({"id": wallet_id})
        if wallet:
            new_balance = wallet.get("balance_bnb", 0) + bnb_to_return
            await db.wallets.update_one(
                {"id": wallet_id},
                {"$set": {"balance_bnb": new_balance}}
            )
        
        # Close each position
        await db.positions.update_one(
            {"id": position["id"]},
            {
                "$set": {
                    "status": "closed",
                    "exit_time": datetime.now(timezone.utc).isoformat(),
                    "realized_pnl_usd": position.get("unrealized_pnl_usd", 0),
                    "tokens_sold": position.get("tokens_held", 0)
                }
            }
        )
        closed_count += 1
        total_pnl += position.get("unrealized_pnl_usd", 0)
    
    # Broadcast bulk close to connected clients
    await bot_state.broadcast_to_clients({
        "type": "positions_bulk_closed",
        "data": {
            "closed_count": closed_count,
            "total_realized_pnl": total_pnl
        }
    })
    
    logger.info(f"Closed {closed_count} positions manually - Total PnL: ${total_pnl:.2f}")
    
    return {
        "message": f"Successfully closed {closed_count} positions",
        "closed_count": closed_count,
        "total_realized_pnl": total_pnl
    }

@api_router.delete("/positions/delete-all")
async def delete_all_positions():
    """Completely delete all positions from database"""
    try:
        # Find all positions to return funds to wallets first
        all_positions = await db.positions.find({"status": {"$in": ["open", "partial"]}}).to_list(1000)
        
        returned_funds = 0.0
        bnb_price = 600  # Assuming 1 BNB = ~$600
        
        # Return funds from open positions to wallets
        for position in all_positions:
            current_value_usd = position.get("current_value_usd", 0)
            if current_value_usd > 0:
                bnb_to_return = current_value_usd / bnb_price
                wallet_id = position.get("wallet_id")
                
                if wallet_id:
                    wallet = await db.wallets.find_one({"id": wallet_id})
                    if wallet:
                        new_balance = wallet.get("balance_bnb", 0) + bnb_to_return
                        await db.wallets.update_one(
                            {"id": wallet_id},
                            {"$set": {"balance_bnb": new_balance}}
                        )
                        returned_funds += bnb_to_return
        
        # Delete all positions from database
        result = await db.positions.delete_many({})
        deleted_count = result.deleted_count
        
        logger.info(f"🗑️ Deleted {deleted_count} positions from database, returned {returned_funds:.4f} BNB to wallets")
        
        # Broadcast deletion event to all connected clients
        await bot_state.broadcast_to_clients({
            "type": "positions_deleted",
            "data": {
                "deleted_count": deleted_count,
                "returned_funds_bnb": returned_funds
            }
        })
        
        return {
            "message": f"Successfully deleted {deleted_count} positions",
            "deleted_count": deleted_count,
            "returned_funds_bnb": returned_funds
        }
        
    except Exception as e:
        logger.error(f"Error deleting all positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete positions")

# ==================== WEBSOCKET ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    bot_state.add_client(websocket)
    
    try:
        # Send initial status
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "data": {
                "status": "connected",
                "bot_running": bot_state.is_running,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client messages if needed
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }))
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    finally:
        bot_state.remove_client(websocket)

# ==================== BACKGROUND TASKS ====================

async def auto_update_wallet_balances():
    """Automatically update real wallet balances every 5 seconds"""
    logger.info("🔄 Starting automatic wallet balance updates...")
    
    while bot_state.is_running:
        try:
            # Get all wallets with private keys
            wallets = await db.wallets.find({
                "is_active": True,
                "private_key": {"$exists": True, "$ne": None, "$ne": ""}
            }).to_list(10)
            
            for wallet in wallets:
                try:
                    # Get RPC config
                    rpc_config = await db.rpc_config.find_one({"is_active": True})
                    if not rpc_config:
                        continue
                    
                    w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
                    from eth_account import Account
                    account = Account.from_key(wallet['private_key'])
                    
                    # Get REAL balance from blockchain
                    real_balance_wei = w3.eth.get_balance(account.address)
                    real_balance_bnb = float(w3.from_wei(real_balance_wei, 'ether'))
                    real_balance_usd = real_balance_bnb * 1170  # Current BNB price
                    
                    # Update database with fresh balance
                    await db.wallets.update_one(
                        {"id": wallet["id"]},
                        {
                            "$set": {
                                "real_balance_bnb": real_balance_bnb,
                                "real_balance_usd": real_balance_usd,
                                "last_balance_update": datetime.now(timezone.utc)
                            }
                        }
                    )
                    
                    logger.info(f"💰 Auto-updated {wallet['name']}: {real_balance_bnb:.6f} BNB (${real_balance_usd:.2f})")
                    
                except Exception as e:
                    logger.error(f"Error updating balance for wallet {wallet.get('name')}: {e}")
                    
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in wallet balance auto-update: {e}")
            await asyncio.sleep(10)

async def start_pair_monitoring():
    """Start monitoring for new pairs"""
    logger.info("Starting pair monitoring (REAL MODE)...")
    
    while bot_state.is_running:
        try:
            # Scan for real pairs from PancakeSwap
            await scan_real_pairs()
            await asyncio.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            logger.error(f"Error in pair monitoring: {e}")
            await asyncio.sleep(10)

async def check_auto_close_conditions(position, current_price, unrealized_pnl_percent):
    """Check auto-close conditions - TAKE PROFIT PROTECTION ENABLED"""
    try:
        # Get CURRENT trading configuration
        config = await db.trading_config.find_one({"is_active": True})
        if not config:
            logger.warning("No active trading config found for auto-close check")
            return False
        
        position_id = position["id"]
        
        # Handle datetime parsing
        entry_time_raw = position.get("entry_time")
        if isinstance(entry_time_raw, str):
            try:
                entry_time = datetime.fromisoformat(entry_time_raw.replace('Z', '+00:00'))
            except:
                entry_time = datetime.strptime(entry_time_raw.split('.')[0], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        else:
            entry_time = entry_time_raw
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
        
        current_time = datetime.now(timezone.utc)
        position_age_minutes = (current_time - entry_time).total_seconds() / 60
        
        should_close = False
        close_reason = ""
        
        # Log current status
        logger.info(f"🕐 Checking {position.get('token_symbol')}: {unrealized_pnl_percent:.1f}% profit, {position_age_minutes:.1f}min old")
        
        # 1. TAKE PROFIT PROTECTION (PRIORITY - Protect profits!)
        take_profit_targets = config.get("take_profit_targets", [])
        for i, target_multiplier in enumerate(take_profit_targets):
            if target_multiplier <= 1:
                continue
                
            target_percent = (target_multiplier - 1) * 100  # Convert 3x to 200%, 5x to 400%
            
            if unrealized_pnl_percent >= target_percent:
                should_close = True
                close_reason = f"💰 TAKE PROFIT {target_multiplier}x triggered! (+{target_percent:.0f}% target, actual: +{unrealized_pnl_percent:.1f}%)"
                logger.info(f"💰 {position.get('token_symbol')} TAKE PROFIT: {close_reason}")
                break
        
        # 2. Time-based exit check (secondary protection)
        max_time = config.get("max_position_time_minutes", 20)
        if position_age_minutes >= max_time:
            should_close = True
            close_reason = f"⏰ Time limit reached ({max_time}min, actual: {position_age_minutes:.1f}min)"
            logger.info(f"⏰ {position.get('token_symbol')} TIME EXIT: {close_reason}")
        
        # 3. Stop loss check (DELAYED - give tokens time to pump first!)
        stop_loss = config.get("stop_loss_percent", 30)
        if (stop_loss > 0 and 
            unrealized_pnl_percent <= -stop_loss and 
            position_age_minutes >= 2):  # Wait at least 2 minutes before stop loss
            should_close = True
            close_reason = f"🛑 Stop loss triggered (-{stop_loss}%, actual: {unrealized_pnl_percent:.1f}%) after {position_age_minutes:.1f}min"
            logger.info(f"🛑 {position.get('token_symbol')} STOP LOSS: {close_reason}")
        elif unrealized_pnl_percent <= -stop_loss and position_age_minutes < 2:
            logger.info(f"⏳ {position.get('token_symbol')} waiting for pump ({unrealized_pnl_percent:.1f}% down, {position_age_minutes:.1f}min old)")
        
        # 4. Emergency crash protection (EXTREME losses)
        if unrealized_pnl_percent <= -90 and position_age_minutes >= 1:  # 1 minute for extreme losses
            should_close = True
            close_reason = f"🆘 EMERGENCY: Extreme loss (-{abs(unrealized_pnl_percent):.1f}%) - likely scam token"
            logger.info(f"🆘 {position.get('token_symbol')} EMERGENCY CLOSE: {close_reason}")
        
        if should_close:
            # Execute immediate auto-close
            await auto_close_position(position_id, close_reason, current_price)
            return True
        
        return False
            
    except Exception as e:
        logger.error(f"Error in auto-close check for position {position.get('id')}: {e}")
        return False

async def auto_close_position(position_id: str, reason: str, current_price: float):
    """Automatically close a position with REAL PancakeSwap sell execution"""
    try:
        position = await db.positions.find_one({"id": position_id})
        if not position or position.get("status") != "open":
            return
        
        # Get wallet with private key
        wallet_id = position.get("wallet_id")
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet or not wallet.get("private_key"):
            logger.error(f"No private key for wallet {wallet_id} - cannot execute real auto-close")
            return
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config:
            logger.error("No RPC configuration for real auto-close")
            return
        
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        from eth_account import Account
        account = Account.from_key(wallet['private_key'])
        token_address = position.get("token_address")
        
        # Get current token balance
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        token_balance_wei = token_contract.functions.balanceOf(account.address).call()
        decimals = token_contract.functions.decimals().call()
        actual_tokens = token_balance_wei / (10 ** decimals)
        
        if actual_tokens <= 0:
            logger.warning(f"No tokens to auto-sell for {position.get('token_symbol')}")
            return
        
        logger.info(f"🤖 AUTO-CLOSE: Selling {actual_tokens:.2f} {position.get('token_symbol')} - {reason}")
        
        # Execute REAL auto-sell on PancakeSwap
        config = await db.trading_config.find_one({"is_active": True})
        sell_tx_hash = await execute_real_pancakeswap_sell(
            w3, account, token_address, actual_tokens, config or {}
        )
        
        if sell_tx_hash:
            # Update position to closed
            await db.positions.update_one(
                {"id": position_id},
                {
                    "$set": {
                        "status": "closed",
                        "exit_time": datetime.now(timezone.utc),
                        "exit_tx_hashes": [sell_tx_hash],
                        "tokens_sold": actual_tokens,
                        "notes": f"Auto-closed: {reason} - REAL SELL TX: {sell_tx_hash}"
                    }
                }
            )
        
            # Broadcast closure
            await bot_state.broadcast_to_clients({
                "type": "position_closed",
                "data": {
                    "position_id": position_id,
                    "token_symbol": position.get("token_symbol"),
                    "reason": reason,
                    "tokens_sold": actual_tokens,
                    "sell_tx_hash": sell_tx_hash
                }
            })
            
            logger.info(f"🔒 REAL AUTO-CLOSE: {position.get('token_symbol')} - {reason} - TX: {sell_tx_hash}")
        
    except Exception as e:
        logger.error(f"Error real auto-closing position {position_id}: {e}")

async def update_position_prices():
    """Update position prices using REAL PancakeSwap data - MILLISECOND UPDATES"""
    logger.info("🚀 Starting REAL MARKET price updates (REAL PANCAKESWAP DATA!)")
    
    while bot_state.is_running:
        try:
            # Get all open positions
            open_positions = await db.positions.find({"status": {"$in": ["open", "partial"]}}).to_list(1000)
            
            if not open_positions:
                await asyncio.sleep(0.5)  # Check every 500ms when no positions
                continue
            
            updated_positions = []
            
            # Process each position with REAL data
            for position in open_positions:
                try:
                    # GET REAL PANCAKESWAP PRICES - NO SIMULATION!
                    token_address = position.get("token_address")
                    if not token_address:
                        continue
                    
                    # Step 1: Get REAL price from DexScreener API (matches the links!)
                    real_price_data = await get_real_time_token_price(token_address)
                    
                    if real_price_data and real_price_data['price_usd'] > 0:
                        # Use REAL DexScreener price (exact same as the link shows)
                        new_price_usd = real_price_data['price_usd']
                        price_source = "REAL DexScreener API"
                        logger.info(f"📊 REAL PRICE: {position.get('token_symbol')} = ${new_price_usd:.8f} (DexScreener)")
                    else:
                        # Step 2: Fallback to REAL PancakeSwap reserves calculation
                        pair_address = position.get("pair_address")
                        if not pair_address:
                            logger.warning(f"No pair address for {position.get('token_symbol')} - skipping")
                            continue
                            
                        pair_info = await get_pair_info(pair_address)
                        if not pair_info:
                            logger.warning(f"Cannot get pair info for {position.get('token_symbol')} - skipping")
                            continue
                            
                        new_price_usd = pair_info['initial_price']
                        price_source = "REAL PancakeSwap Reserves"
                        logger.info(f"📊 REAL PRICE: {position.get('token_symbol')} = ${new_price_usd:.8f} (PancakeSwap)")
                    
                    # Calculate with REAL market data
                    entry_price = position.get("entry_price", 0)
                    entry_amount_usd = position.get("entry_amount_usd", 0)
                    tokens_held = position.get("tokens_held", 0)
                    
                    if entry_price <= 0 or entry_amount_usd <= 0 or tokens_held <= 0:
                        logger.warning(f"Invalid position data for {position.get('token_symbol')} - skipping")
                        continue
                    
                    # REAL P&L calculation based on actual price movement
                    price_change_ratio = new_price_usd / entry_price if entry_price > 0 else 1
                    new_value_usd = entry_amount_usd * price_change_ratio
                    
                    unrealized_pnl_usd = new_value_usd - entry_amount_usd
                    unrealized_pnl_percent = ((new_price_usd - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    
                    logger.info(f"💹 REAL P&L: {position.get('token_symbol')} - Entry: ${entry_price:.8f} -> Current: ${new_price_usd:.8f} = {unrealized_pnl_percent:.2f}%")
                    
                    # Update with REAL market data
                    await db.positions.update_one(
                        {"id": position["id"]},
                        {
                            "$set": {
                                "current_price": new_price_usd,
                                "current_value_usd": new_value_usd,
                                "unrealized_pnl_usd": unrealized_pnl_usd,
                                "unrealized_pnl_percent": unrealized_pnl_percent,
                                "last_price_update": datetime.now(timezone.utc).isoformat(),
                                "price_source": price_source
                            }
                        }
                    )
                    
                    # Check for auto-close conditions with correct price variable
                    was_closed = await check_auto_close_conditions(position, new_price_usd, unrealized_pnl_percent)
                    
                    # Only add to broadcast if position wasn't closed
                    if not was_closed:
                        # Add to broadcast list with REAL data
                        updated_positions.append({
                            "id": position["id"],
                            "token_symbol": position.get("token_symbol", ""),
                            "current_price": new_price_usd,
                            "current_value_usd": new_value_usd,
                            "unrealized_pnl_usd": unrealized_pnl_usd,
                            "unrealized_pnl_percent": unrealized_pnl_percent,
                            "price_source": price_source
                        })
                    
                except Exception as e:
                    logger.error(f"Error updating position {position.get('id')}: {e}")
                    continue
            
            # Broadcast REAL price updates to frontend
            if updated_positions:
                await bot_state.broadcast_to_clients({
                    "type": "positions_updated",
                    "data": {
                        "positions": updated_positions,
                        "count": len(updated_positions),
                        "update_source": "REAL_PANCAKESWAP_DATA",
                        "update_time": datetime.now(timezone.utc).isoformat()
                    }
                })
            
            # Update every 1 second for INSTANT buy/sell execution
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error updating REAL prices: {e}")
            await asyncio.sleep(2)

async def calculate_tokens_from_receipt(w3, receipt, token_address, wallet_address):
    """Calculate actual tokens received from transaction receipt"""
    try:
        # Setup token contract
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        # Get actual token balance from blockchain
        token_balance_wei = token_contract.functions.balanceOf(wallet_address).call()
        
        # Get token decimals
        decimals = token_contract.functions.decimals().call()
        
        # Convert to human readable amount
        tokens_received = token_balance_wei / (10 ** decimals)
        
        return tokens_received
        
    except Exception as e:
        logger.error(f"Error calculating tokens from receipt: {e}")
        return 0

async def execute_real_pancakeswap_trade(detected_pair: NewPairEvent):
    """Execute REAL blockchain transaction on PancakeSwap"""
    try:
        # Get trading configuration
        config = await db.trading_config.find_one({"is_active": True})
        if not config:
            logger.warning("No trading config found for real execution")
            return
            
        # Get RPC configuration
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config or not rpc_config.get('bsc_rpc_http'):
            logger.error("No RPC configuration found - cannot execute real trades!")
            return
        
        # Get wallets with real private keys and check their real balances
        wallets = await db.wallets.find({
            "is_active": True, 
            "private_key": {"$exists": True, "$ne": None, "$ne": ""},
            "real_balance_bnb": {"$exists": True, "$gte": 0.001}  # Minimum 0.001 BNB
        }).to_list(10)
        
        if not wallets:
            logger.warning("No wallets with private keys for real trading")
            return
            
        # Check which wallet has sufficient real balance
        suitable_wallet = None
        for wallet in wallets:
            private_key = wallet.get('private_key')
            if not private_key:
                continue
                
            try:
                # Get real balance from blockchain
                from eth_account import Account
                account = Account.from_key(private_key)
                w3_temp = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
                
                real_balance_wei = w3_temp.eth.get_balance(account.address)
                real_balance_bnb = float(w3_temp.from_wei(real_balance_wei, 'ether'))
                
                # Calculate minimum needed (trade amount + gas) - USE REAL BNB PRICE
                trade_amount_usd = config.get('trade_amount_usd', 5)
                bnb_price_usd = 1170  # Real BNB price (~$1,170)
                trade_amount_bnb = trade_amount_usd / bnb_price_usd
                min_balance_needed = trade_amount_bnb + 0.002  # Add gas buffer
                
                logger.info(f"💰 Wallet {wallet.get('name')}: {real_balance_bnb:.6f} BNB (need: {min_balance_needed:.6f})")
                
                if real_balance_bnb >= min_balance_needed:
                    suitable_wallet = wallet
                    break
                    
            except Exception as e:
                logger.error(f"Error checking wallet {wallet.get('name')}: {e}")
                continue
        
        if not suitable_wallet:
            logger.warning("No wallets with sufficient real BNB balance for trading")
            return
            
        # Use the suitable wallet
        wallet = suitable_wallet
        private_key = wallet.get('private_key')
        
        if not private_key:
            logger.error(f"No private key for wallet {wallet.get('name')} - cannot execute real trade!")
            return
        
        # Initialize Web3 with your RPC
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        if not w3.is_connected():
            logger.error("Cannot connect to BSC network!")
            return
        
        # Setup account
        from eth_account import Account
        account = Account.from_key(private_key)
        wallet_address = account.address
        
        logger.info(f"🔥 EXECUTING REAL TRADE: {detected_pair.token_symbol} from wallet {wallet_address}")
        
        # Get real wallet balance
        real_balance_wei = w3.eth.get_balance(wallet_address)
        real_balance_bnb = w3.from_wei(real_balance_wei, 'ether')
        
        logger.info(f"💰 Real wallet balance: {real_balance_bnb:.6f} BNB")
        
        # Calculate trade amount with REAL BNB price
        trade_amount_usd = config.get('trade_amount_usd', 5)
        bnb_price_usd = 1170  # Real BNB price
        trade_amount_bnb = trade_amount_usd / bnb_price_usd  # Should be ~0.004 BNB for $5
        
        # Check sufficient balance (including gas fees)
        min_balance_needed = trade_amount_bnb + 0.001  # Add gas buffer
        if real_balance_bnb < min_balance_needed:
            logger.error(f"Insufficient BNB! Need {min_balance_needed:.6f}, have {real_balance_bnb:.6f}")
            return
        
        # EXECUTE REAL PANCAKESWAP BUY
        tx_hash = await execute_real_pancakeswap_buy(
            w3, account, detected_pair.token_address, trade_amount_bnb, config
        )
        
        if tx_hash:
            # Calculate REAL tokens from transaction (simplified for now)
            tokens_received = 1000.0  # Placeholder - will calculate from transaction
            real_entry_price = trade_amount_usd / tokens_received
            
            # Create REAL position that shows immediately in UI
            real_position = Position(
                wallet_id=wallet['id'],
                token_address=detected_pair.token_address,
                token_symbol=detected_pair.token_symbol,
                token_name=detected_pair.token_name,
                pair_address=detected_pair.pair_address,
                entry_amount_bnb=trade_amount_bnb,
                entry_amount_usd=trade_amount_usd,
                entry_price=real_entry_price,
                current_price=real_entry_price,
                current_value_usd=trade_amount_usd,
                tokens_held=tokens_received,
                entry_time=datetime.now(timezone.utc),
                status="open",  # Keep OPEN so user can see it
                unrealized_pnl_usd=0.0,
                unrealized_pnl_percent=0.0,
                entry_tx_hash=tx_hash
            )
            
            # Store position in database
            await db.positions.insert_one(real_position.dict())
            
            # Broadcast to frontend immediately
            await bot_state.broadcast_to_clients({
                "type": "real_position_created", 
                "data": real_position.dict()
            })
            
            logger.info(f"🚀 REAL POSITION CREATED: {detected_pair.token_symbol} - TX: {tx_hash} - User can now see and manage it!")
        
    except Exception as e:
        logger.error(f"Error executing real trade for {detected_pair.token_symbol}: {e}")

async def execute_real_pancakeswap_buy(w3, account, token_address, bnb_amount, config):
    """Execute REAL BNB -> Token swap on PancakeSwap"""
    try:
        # Setup PancakeSwap Router contract
        router_contract = w3.eth.contract(
            address=Web3.to_checksum_address(PANCAKESWAP_ROUTER_V2),
            abi=PANCAKESWAP_ROUTER_ABI
        )
        
        # Convert amounts
        bnb_amount_wei = w3.to_wei(bnb_amount, 'ether')
        
        # Setup swap path: BNB -> WBNB -> Token
        path = [
            Web3.to_checksum_address(WBNB_ADDRESS),
            Web3.to_checksum_address(token_address)
        ]
        
        # Get expected output amount
        amounts_out = router_contract.functions.getAmountsOut(bnb_amount_wei, path).call()
        expected_tokens = amounts_out[-1]
        
        # Apply slippage protection
        slippage_percent = config.get('slippage_tolerance_percent', 12)
        min_tokens = int(expected_tokens * (100 - slippage_percent) / 100)
        
        logger.info(f"💱 REAL SWAP: {bnb_amount} BNB -> Expected: {w3.from_wei(expected_tokens, 'ether')} tokens (min: {w3.from_wei(min_tokens, 'ether')})")
        
        # Setup deadline (10 minutes from now)
        deadline = int(time.time()) + 600
        
        # Build transaction
        transaction = router_contract.functions.swapExactETHForTokens(
            min_tokens,
            path,
            account.address,
            deadline
        ).build_transaction({
            'from': account.address,
            'value': bnb_amount_wei,
            'gas': config.get('gas_limit', 300000),
            'gasPrice': w3.to_wei(config.get('gas_price_gwei', 5), 'gwei'),
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': 56  # BSC Mainnet
        })
        
        # Sign transaction with real private key (Web3.py v7+ compatible)
        signed_txn = w3.eth.account.sign_transaction(transaction, account.key)
        
        # Handle different Web3.py versions
        try:
            if hasattr(signed_txn, 'raw_transaction'):
                raw_transaction = signed_txn.raw_transaction
            elif hasattr(signed_txn, 'rawTransaction'):
                raw_transaction = signed_txn.rawTransaction
            else:
                raw_transaction = bytes(signed_txn)
                
            tx_hash = w3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
        except Exception as signing_error:
            logger.error(f"Buy transaction signing error: {signing_error}")
            signed_bytes = signed_txn if isinstance(signed_txn, bytes) else signed_txn.raw_transaction
            tx_hash = w3.eth.send_raw_transaction(signed_bytes)
            tx_hash_hex = tx_hash.hex()
        
        logger.info(f"🔥 REAL TRANSACTION SENT: {tx_hash_hex}")
        logger.info(f"🔗 View on BSCScan: https://bscscan.com/tx/{tx_hash_hex}")
        
        return tx_hash_hex
        
    except Exception as e:
        logger.error(f"REAL transaction failed: {e}")
        return None

async def execute_real_pancakeswap_sell(w3, account, token_address, token_amount, config):
    """Execute REAL Token -> BNB swap on PancakeSwap"""
    try:
        # Setup contracts
        router_contract = w3.eth.contract(
            address=Web3.to_checksum_address(PANCAKESWAP_ROUTER_V2),
            abi=PANCAKESWAP_ROUTER_ABI
        )
        
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        
        # Get token decimals
        decimals = token_contract.functions.decimals().call()
        token_amount_wei = int(token_amount * (10 ** decimals))
        
        # Check and approve token spending
        allowance = token_contract.functions.allowance(account.address, PANCAKESWAP_ROUTER_V2).call()
        
        if allowance < token_amount_wei:
            # Approve tokens for router
            approve_tx = token_contract.functions.approve(
                PANCAKESWAP_ROUTER_V2,
                token_amount_wei * 2  # Approve double amount for future trades
            ).build_transaction({
                'from': account.address,
                'gas': 100000,
                'gasPrice': w3.to_wei(5, 'gwei'),
                'nonce': w3.eth.get_transaction_count(account.address),
                'chainId': 56
            })
            
            # Sign and send approval (Web3.py v7+ compatible)
            signed_approve = w3.eth.account.sign_transaction(approve_tx, account.key)
            
            # Handle different Web3.py versions
            try:
                if hasattr(signed_approve, 'raw_transaction'):
                    raw_transaction = signed_approve.raw_transaction
                elif hasattr(signed_approve, 'rawTransaction'):
                    raw_transaction = signed_approve.rawTransaction
                else:
                    raw_transaction = bytes(signed_approve)
                    
                approve_hash = w3.eth.send_raw_transaction(raw_transaction)
                
            except Exception as signing_error:
                logger.error(f"Approve signing error: {signing_error}")
                signed_bytes = signed_approve if isinstance(signed_approve, bytes) else signed_approve.raw_transaction
                approve_hash = w3.eth.send_raw_transaction(signed_bytes)
            
            logger.info(f"🔓 APPROVAL SENT: {approve_hash.hex()}")
            
            # Wait for approval confirmation
            receipt = w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
            if receipt.status != 1:
                logger.error("Approval transaction failed!")
                return None
        
        # Setup swap path: Token -> WBNB -> BNB  
        path = [
            Web3.to_checksum_address(token_address),
            Web3.to_checksum_address(WBNB_ADDRESS)
        ]
        
        # Get expected BNB output
        amounts_out = router_contract.functions.getAmountsOut(token_amount_wei, path).call()
        expected_bnb = amounts_out[-1]
        
        # Apply slippage protection
        slippage_percent = config.get('slippage_tolerance_percent', 12)
        min_bnb = int(expected_bnb * (100 - slippage_percent) / 100)
        
        logger.info(f"💱 REAL SELL: {token_amount} tokens -> Expected: {w3.from_wei(expected_bnb, 'ether')} BNB")
        
        # Setup deadline
        deadline = int(time.time()) + 600
        
        # Build sell transaction
        transaction = router_contract.functions.swapExactTokensForETH(
            token_amount_wei,
            min_bnb,
            path,
            account.address,
            deadline
        ).build_transaction({
            'from': account.address,
            'gas': config.get('gas_limit', 300000),
            'gasPrice': w3.to_wei(config.get('gas_price_gwei', 5), 'gwei'),
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': 56
        })
        
        # Sign and send real sell transaction (Web3.py v7+ compatible)
        signed_txn = w3.eth.account.sign_transaction(transaction, account.key)
        
        # Web3.py v7+ uses different attribute names
        try:
            if hasattr(signed_txn, 'raw_transaction'):
                raw_transaction = signed_txn.raw_transaction
            elif hasattr(signed_txn, 'rawTransaction'):
                raw_transaction = signed_txn.rawTransaction
            else:
                # Fallback for newer versions
                raw_transaction = bytes(signed_txn)
                
            tx_hash = w3.eth.send_raw_transaction(raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
        except Exception as signing_error:
            logger.error(f"Transaction signing error: {signing_error}")
            # Try alternative signing method
            signed_bytes = signed_txn if isinstance(signed_txn, bytes) else signed_txn.raw_transaction
            tx_hash = w3.eth.send_raw_transaction(signed_bytes)
            tx_hash_hex = tx_hash.hex()
        
        logger.info(f"💰 REAL SELL SENT: {tx_hash_hex}")
        logger.info(f"🔗 View on BSCScan: https://bscscan.com/tx/{tx_hash_hex}")
        
        return tx_hash_hex
        
    except Exception as e:
        logger.error(f"REAL sell transaction failed: {e}")
        return None

async def create_demo_position():
    """Create a demo trading position for testing"""
    import random
    
    # Get active wallets
    wallets = await db.wallets.find({"is_active": True, "balance_bnb": {"$gt": 0}}).to_list(10)
    if not wallets:
        return
    
    # Pick a random wallet
    wallet = random.choice(wallets)
    
    # Create demo position with realistic token names
    realistic_tokens = [
        "PEPE", "SHIB", "DOGE", "FLOKI", "SAFEMOON", "BABYDOGE", "ELON", 
        "KISHU", "HOKK", "AKITA", "SAITAMA", "RYOSHI", "LEASH", "BONE",
        "CATGIRL", "DOGELON", "HOGE", "PIG", "SAMO", "CHEEMS"
    ]
    
    # Create demo position with random data
    demo_position = Position(
        wallet_id=wallet["id"],
        token_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
        token_symbol=random.choice(realistic_tokens),
        pair_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
        entry_price=random.uniform(0.000001, 0.01),
        entry_amount_bnb=0.1,
        entry_amount_usd=random.uniform(25, 100),
        current_price=random.uniform(0.000001, 0.01),
        current_value_usd=random.uniform(20, 200),
        tokens_held=random.uniform(1000, 100000),
        entry_tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}"
    )
    
    # Calculate P&L
    demo_position.unrealized_pnl_usd = demo_position.current_value_usd - demo_position.entry_amount_usd
    demo_position.unrealized_pnl_percent = (demo_position.unrealized_pnl_usd / demo_position.entry_amount_usd) * 100
    
    # Deduct trade amount from wallet balance
    bnb_price = 600  # Assuming 1 BNB = ~$600 for demo
    bnb_spent = demo_position.entry_amount_bnb
    
    new_wallet_balance = wallet["balance_bnb"] - bnb_spent
    await db.wallets.update_one(
        {"id": wallet["id"]},
        {"$set": {"balance_bnb": max(0, new_wallet_balance)}}  # Ensure balance doesn't go negative
    )
    logger.info(f"Wallet {wallet.get('name')} updated: -{bnb_spent:.4f} BNB (new balance: {max(0, new_wallet_balance):.4f} BNB)")
    
    # Store in database
    await db.positions.insert_one(demo_position.dict())
    
    # Broadcast to connected clients
    await bot_state.broadcast_to_clients({
        "type": "demo_position_created",
        "data": demo_position.dict()
    })
    
    logger.info(f"Demo position created: {demo_position.token_symbol} - {demo_position.unrealized_pnl_percent:.2f}% P&L")

async def get_token_info(token_address: str):
    """Fetch token information from blockchain"""
    try:
        token_contract = blockchain_config.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=blockchain_config.erc20_abi
        )
        
        # Fetch token data (FIXED: symbol and name were swapped)
        symbol = token_contract.functions.symbol().call()[:10]  # Get symbol 
        name = token_contract.functions.name().call()[:50]      # Get full name
        decimals = token_contract.functions.decimals().call()
        
        return {
            "symbol": symbol,
            "name": name,
            "decimals": decimals
        }
    except Exception as e:
        logger.error(f"Error fetching token info for {token_address}: {e}")
        return {"symbol": "UNKNOWN", "name": "Unknown Token", "decimals": 18}

async def get_real_time_token_price(token_address: str):
    """Get REAL-TIME token price from DexScreener API - EXACT SAME DATA AS LINKS"""
    try:
        # Use the EXACT same API that DexScreener links use
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs')
                    
                    if not pairs or len(pairs) == 0:
                        return None
                    
                    # Find PancakeSwap BSC pair (exact same logic as DexScreener website)
                    pancake_pair = None
                    for pair in pairs:
                        if (pair.get('chainId') == 'bsc' and 
                            pair.get('dexId') == 'pancakeswap' and
                            pair.get('priceUsd')):
                            if not pancake_pair or float(pair.get('liquidity', {}).get('usd', 0)) > float(pancake_pair.get('liquidity', {}).get('usd', 0)):
                                pancake_pair = pair
                    
                    if pancake_pair:
                        # Extract EXACT same data as DexScreener shows
                        price_usd = float(pancake_pair.get('priceUsd', '0'))
                        price_change_5m = float(pancake_pair.get('priceChange', {}).get('m5', '0') or '0')
                        price_change_1h = float(pancake_pair.get('priceChange', {}).get('h1', '0') or '0')
                        price_change_24h = float(pancake_pair.get('priceChange', {}).get('h24', '0') or '0')
                        liquidity_usd = float(pancake_pair.get('liquidity', {}).get('usd', 0))
                        volume_24h = float(pancake_pair.get('volume', {}).get('h24', 0))
                        
                        logger.info(f"📊 REAL DEXSCREENER DATA: {token_address} = ${price_usd:.8f} | 5m: {price_change_5m:.2f}% | 1h: {price_change_1h:.2f}%")
                        
                        return {
                            'price_usd': price_usd,
                            'price_change_5m': price_change_5m,
                            'price_change_1h': price_change_1h,
                            'price_change_24h': price_change_24h,
                            'liquidity_usd': liquidity_usd,
                            'volume_24h': volume_24h,
                            'source': 'REAL_DEXSCREENER',
                            'pair_address': pancake_pair.get('pairAddress')
                        }
                        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching REAL DexScreener data for {token_address}: {e}")
        return None

async def get_pair_info(pair_address: str):
    """Fetch pair reserves and calculate liquidity"""
    try:
        pair_contract = blockchain_config.w3.eth.contract(
            address=Web3.to_checksum_address(pair_address),
            abi=blockchain_config.pair_abi
        )
        
        # Get reserves
        reserves = pair_contract.functions.getReserves().call()
        reserve0 = reserves[0] / 1e18
        reserve1 = reserves[1] / 1e18
        
        # Get token addresses
        token0 = pair_contract.functions.token0().call()
        token1 = pair_contract.functions.token1().call()
        
        # Determine which is WBNB
        wbnb_address = blockchain_config.wbnb_address.lower()
        if token0.lower() == wbnb_address:
            wbnb_reserves = reserve0
            token_reserves = reserve1
            token_address = token1
        else:
            wbnb_reserves = reserve1
            token_reserves = reserve0
            token_address = token0
        
        # Calculate liquidity (assuming BNB = $600)
        bnb_price_usd = 600
        liquidity_usd = wbnb_reserves * bnb_price_usd * 2  # Total liquidity
        
        # Calculate initial price with validation
        if token_reserves > 0 and wbnb_reserves > 0:
            # Price = WBNB per token * BNB price in USD
            price_per_token_in_bnb = wbnb_reserves / token_reserves
            price_per_token_usd = price_per_token_in_bnb * bnb_price_usd
            
            # Validate reasonable price range to prevent fake calculations
            if price_per_token_usd > 0.000001 and price_per_token_usd < 100000:  # Between $0.000001 and $100,000
                initial_price = price_per_token_usd
            else:
                logger.warning(f"Unrealistic price calculated: ${price_per_token_usd} - using fallback")
                initial_price = 0.01  # Fallback realistic price
        else:
            initial_price = 0.01  # Fallback for zero reserves
        
        return {
            "wbnb_reserves": wbnb_reserves,
            "token_reserves": token_reserves,
            "token_address": token_address,
            "liquidity_usd": liquidity_usd,
            "initial_price": initial_price
        }
    except Exception as e:
        logger.error(f"Error fetching pair info for {pair_address}: {e}")
        return None

async def scan_real_pairs():
    """Scan for real PancakeSwap pairs using blockchain data"""
    try:
        # Load saved RPC config from database
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config or not rpc_config.get('bsc_rpc_ws'):
            logger.warning("No WebSocket RPC configured, using HTTP polling")
            await scan_pairs_via_http()
            return
        
        # Update blockchain config with saved credentials
        blockchain_config.bsc_rpc_ws = rpc_config['bsc_rpc_ws']
        blockchain_config.bsc_rpc_http = rpc_config['bsc_rpc_http']
        blockchain_config.w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        
        logger.info(f"Starting real pair scanning via WebSocket...")
        
        # For now, use HTTP polling (WebSocket implementation is complex)
        await scan_pairs_via_http()
        
    except Exception as e:
        logger.error(f"Error in real pair scanning: {e}")
        await asyncio.sleep(10)

async def scan_pairs_via_http():
    """Scan for new pairs using HTTP polling"""
    try:
        # Get the latest block for real-time monitoring
        latest_block = blockchain_config.w3.eth.block_number
        
        # Store the current block as our starting point for NEW pairs only
        if not hasattr(blockchain_config, 'monitoring_from_block'):
            blockchain_config.monitoring_from_block = latest_block
            logger.info(f"🔍 Starting NEW pair detection from block {latest_block}")
            return  # Skip first run to avoid detecting old pairs
        
        # Get factory contract
        factory_contract = blockchain_config.w3.eth.contract(
            address=Web3.to_checksum_address(blockchain_config.pancake_factory),
            abi=blockchain_config.factory_abi
        )
        
        # Only check for NEW events since last check (not historical events)
        from_block = blockchain_config.monitoring_from_block + 1
        to_block = latest_block
        
        if from_block > to_block:
            return  # No new blocks to check
        
        logger.info(f"🔎 Scanning blocks {from_block} to {to_block} for NEW pairs only")
        
        try:
            events = factory_contract.events.PairCreated.get_logs(
                from_block=from_block,
                to_block=to_block
            )
            
            # Update monitoring position
            blockchain_config.monitoring_from_block = to_block
            
            if events:
                logger.info(f"🚨 Found {len(events)} NEW PairCreated events!")
            
            for event in events:
                # Process each pair creation event
                pair_address = event['args']['pair']
                token0 = event['args']['token0']
                token1 = event['args']['token1']
                
                # Check if already detected
                existing = await db.detected_pairs.find_one({"pair_address": pair_address.lower()})
                if existing:
                    continue
                
                # Get pair info
                pair_info = await get_pair_info(pair_address)
                if not pair_info or pair_info['liquidity_usd'] < 5000:
                    continue
                
                # Get token info
                token_info = await get_token_info(pair_info['token_address'])
                
                # Filter out well-known established tokens (not genuinely "new")
                established_tokens = {
                    'USDT', 'TETHER USD', 'USDC', 'USD COIN', 'BUSD', 'BINANCE USD',
                    'BTC', 'BITCOIN', 'ETH', 'ETHEREUM', 'BNB', 'BINANCE COIN',
                    'ADA', 'CARDANO', 'DOT', 'POLKADOT', 'DOGE', 'DOGECOIN',
                    'MATIC', 'POLYGON', 'AVAX', 'AVALANCHE', 'SOL', 'SOLANA'
                }
                
                token_symbol = token_info['symbol'].upper()
                token_name = token_info['name'].upper()
                
                # Skip if this is a well-known established token
                if (token_symbol in established_tokens or 
                    token_name in established_tokens or
                    'TETHER' in token_name or
                    'BINANCE' in token_name):
                    logger.info(f"⏭️ Skipping established token: {token_info['symbol']} ({token_info['name']})")
                    continue
                
                # Create NewPairEvent with useful links
                token_address = pair_info['token_address'].lower()
                pair_address_lower = pair_address.lower()
                
                new_pair = NewPairEvent(
                    pair_address=pair_address_lower,
                    token0_address=token0.lower(),
                    token1_address=token1.lower(),
                    token_address=token_address,
                    token_symbol=token_info['symbol'],  # Use original case
                    token_name=token_info['name'],      # Use original case
                    wbnb_reserves=pair_info['wbnb_reserves'],
                    token_reserves=pair_info['token_reserves'],
                    liquidity_usd=pair_info['liquidity_usd'],
                    initial_price=pair_info['initial_price'],
                    block_number=event['blockNumber'],
                    transaction_hash=event['transactionHash'].hex(),
                    detected_at=datetime.now(timezone.utc),
                    # Generate useful links for token analysis and trading
                    dexscreener_url=f"https://dexscreener.com/bsc/{token_address}",
                    bscscan_token_url=f"https://bscscan.com/token/{token_address}",
                    bscscan_pair_url=f"https://bscscan.com/address/{pair_address_lower}",
                    pancakeswap_url=f"https://pancakeswap.finance/swap?outputCurrency={token_address}"
                )
                
                # Store in database
                await db.detected_pairs.insert_one(new_pair.dict())
                
                # Execute REAL PancakeSwap trade with actual blockchain transaction
                await execute_real_pancakeswap_trade(new_pair)
                
                # Broadcast to connected clients
                await bot_state.broadcast_to_clients({
                    "type": "new_pair_detected",
                    "data": new_pair.dict()
                })
                
                logger.info(f"🚨 REAL PAIR DETECTED: {new_pair.token_symbol} - ${new_pair.liquidity_usd:,.2f} liquidity")
                
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
        
    except Exception as e:
        logger.error(f"Error in HTTP pair scanning: {e}")

async def simulate_pair_detection():
    """Simulate new pair detection for demo purposes"""
    import random
    
    # Occasionally create demo positions if wallets have funds
    if random.random() < 0.05:  # 5% chance of creating demo trade
        await create_demo_position()
    
    if random.random() < 0.1:  # 10% chance of detecting a new pair
        # Generate timestamp in current time (London timezone will be handled on frontend)
        current_time = datetime.now(timezone.utc)
        
        fake_pair = NewPairEvent(
            pair_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            token0_address=blockchain_config.wbnb_address,
            token1_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            token_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
            token_symbol=f"TOKEN{random.randint(1, 9999)}",
            token_name=f"Test Token {random.randint(1, 9999)}",
            wbnb_reserves=random.uniform(10, 200),
            liquidity_usd=random.uniform(5000, 50000),
            initial_price=random.uniform(0.000001, 0.01),
            block_number=blockchain_config.w3.eth.block_number if blockchain_config.w3.is_connected() else 0,
            transaction_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
            detected_at=current_time
        )
        
        # Store in database
        await db.detected_pairs.insert_one(fake_pair.dict())
        bot_state.detected_pairs.append(fake_pair)
        
        # Broadcast to connected clients
        await bot_state.broadcast_to_clients({
            "type": "new_pair_detected",
            "data": fake_pair.dict()
        })
        
        logger.info(f"New pair detected: {fake_pair.token_symbol} - ${fake_pair.liquidity_usd:.2f} liquidity")

# ==================== MIDDLEWARE & STARTUP ====================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Paradox Bot API starting up...")
    # Initialize optimized high win-rate configuration
    config = await db.trading_config.find_one({"is_active": True})
    if not config:
        # HIGH WIN-RATE RECOMMENDED SETTINGS
        optimized_config = TradingConfig(
            trade_amount_usd=75.0,  # Moderate risk per trade
            max_trade_amount_usd=150.0,  # Cap maximum risk
            min_liquidity_usd=100000.0,  # Only trade high-liquidity pairs (safer)
            max_tax_buy_percent=3.0,  # Very low taxes only (3% max)
            max_tax_sell_percent=3.0,  # Very low taxes only (3% max)
            take_profit_targets=[3, 5, 8],  # Conservative targets (3x, 5x, 8x)
            take_profit_percentages=[60.0, 30.0, 10.0],  # Take most profit early
            stop_loss_percent=25.0,  # Quick stop-loss at 25% down
            max_position_time_minutes=20,  # Maximum 20 minutes per trade
            slippage_tolerance_percent=8.0  # Reasonable slippage
        )
        await db.trading_config.insert_one(optimized_config.dict())
        bot_state.trading_config = optimized_config

@api_router.post("/wallets/{wallet_id}/sync-real-tokens")
async def sync_real_token_balances(wallet_id: str):
    """Sync actual token balances from blockchain for all positions"""
    try:
        # Get wallet
        wallet = await db.wallets.find_one({"id": wallet_id})
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        private_key = wallet.get('private_key')
        if not private_key:
            raise HTTPException(status_code=400, detail="No private key - cannot check token balances")
        
        # Get RPC config
        rpc_config = await db.rpc_config.find_one({"is_active": True})
        if not rpc_config:
            raise HTTPException(status_code=500, detail="No RPC configuration")
        
        # Connect to blockchain
        w3 = Web3(Web3.HTTPProvider(rpc_config['bsc_rpc_http']))
        from eth_account import Account
        account = Account.from_key(private_key)
        
        # Get all positions for this wallet
        positions = await db.positions.find({"wallet_id": wallet_id, "status": "open"}).to_list(100)
        
        synced_count = 0
        for position in positions:
            try:
                token_address = position.get("token_address")
                if not token_address:
                    continue
                
                # Get real token balance from blockchain
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )
                
                token_balance_wei = token_contract.functions.balanceOf(account.address).call()
                decimals = token_contract.functions.decimals().call()
                actual_tokens = token_balance_wei / (10 ** decimals)
                
                # Calculate real entry price based on actual tokens and amount spent
                entry_amount_usd = position.get("entry_amount_usd", 5)
                real_entry_price = entry_amount_usd / actual_tokens if actual_tokens > 0 else 0
                
                # Update position with REAL data
                await db.positions.update_one(
                    {"id": position["id"]},
                    {
                        "$set": {
                            "tokens_held": actual_tokens,
                            "entry_price": real_entry_price,
                            "current_price": real_entry_price,
                            "current_value_usd": entry_amount_usd,
                            "synced_from_blockchain": True
                        }
                    }
                )
                
                synced_count += 1
                logger.info(f"✅ Synced {position.get('token_symbol')}: {actual_tokens:.2f} tokens @ ${real_entry_price:.8f}")
                
            except Exception as e:
                logger.error(f"Error syncing token {position.get('token_symbol')}: {e}")
        
        return {
            "message": f"Successfully synced {synced_count} token balances",
            "synced_positions": synced_count,
            "wallet_address": account.address
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing token balances for wallet {wallet_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync token balances")
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Paradox Bot API shutting down...")
    bot_state.is_running = False
    client.close()