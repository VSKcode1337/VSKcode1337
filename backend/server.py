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

# ERC20 Token ABI (essential functions)
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
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
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
    balance_bnb: float = 0.0
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
    # Return wallets without private keys for security
    wallet_responses = []
    for wallet in wallets:
        wallet.pop('_id', None)  # Remove MongoDB ObjectId
        wallet.pop('private_key', None)  # Remove private key for security
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
    """Get trading statistics, optionally filtered by wallet_id"""
    query = {}
    if wallet_id:
        query["wallet_id"] = wallet_id
    
    # Get positions for statistics
    all_positions = await db.positions.find(query).to_list(1000)
    open_positions = [p for p in all_positions if p.get("status") in ["open", "partial"]]
    closed_positions = [p for p in all_positions if p.get("status") == "closed"]
    
    # Calculate wallet-specific stats
    total_trades = len(closed_positions)
    winning_trades = len([p for p in closed_positions if (p.get("realized_pnl_usd", 0) + p.get("unrealized_pnl_usd", 0)) > 0])
    losing_trades = total_trades - winning_trades
    
    realized_pnl = sum(p.get("realized_pnl_usd", 0) + p.get("unrealized_pnl_usd", 0) for p in closed_positions)
    unrealized_pnl = sum(p.get("unrealized_pnl_usd", 0) for p in open_positions)
    total_pnl = realized_pnl + unrealized_pnl
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Get global pairs detected count (not wallet-specific)
    global_pairs_detected = await db.detected_pairs.count_documents({})
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "total_pnl_usd": total_pnl,
        "realized_pnl_usd": realized_pnl,
        "unrealized_pnl_usd": unrealized_pnl,
        "win_rate_percent": win_rate,
        "pairs_detected": global_pairs_detected,  # Global count
        "pairs_traded": total_trades,  # Wallet-specific
        "active_positions": len(open_positions),
        "wallet_filtered": wallet_id is not None
    }

@api_router.delete("/wallets/{wallet_id}")
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
    position = await db.positions.find_one({"id": position_id})
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # For demo positions, simulate closing
    if position.get("status") != "closed":
        # Calculate final value to return to wallet
        current_value_usd = position.get("current_value_usd", 0)
        entry_amount_usd = position.get("entry_amount_usd", 0)
        realized_pnl_usd = position.get("unrealized_pnl_usd", 0)
        
        # Convert USD back to BNB (assuming 1 BNB = ~$600 for demo)
        bnb_price = 600  # You can update this with real price later
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
            logger.info(f"Wallet {wallet.get('name')} updated: +{bnb_to_return:.4f} BNB (new balance: {new_balance:.4f} BNB)")
        
        # Update position status to closed
        await db.positions.update_one(
            {"id": position_id},
            {
                "$set": {
                    "status": "closed",
                    "exit_time": datetime.now(timezone.utc).isoformat(),
                    "realized_pnl_usd": realized_pnl_usd,
                    "tokens_sold": position.get("tokens_held", 0)
                }
            }
        )
        
        # Broadcast position close to connected clients
        await bot_state.broadcast_to_clients({
            "type": "position_closed",
            "data": {
                "position_id": position_id,
                "token_symbol": position.get("token_symbol"),
                "realized_pnl": realized_pnl_usd,
                "wallet_id": wallet_id,
                "bnb_returned": bnb_to_return
            }
        })
        
        logger.info(f"Position closed manually: {position.get('token_symbol')} - PnL: ${realized_pnl_usd:.2f}")
        
        return {
            "message": "Position closed successfully",
            "position_id": position_id,
            "realized_pnl": realized_pnl_usd,
            "bnb_returned": bnb_to_return
        }
    else:
        raise HTTPException(status_code=400, detail="Position is already closed")

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
    """Check if position should be auto-closed based on CURRENT trading rules"""
    try:
        # Get CURRENT trading configuration (refresh every check)
        config = await db.trading_config.find_one({"is_active": True})
        if not config:
            logger.warning("No active trading config found for auto-close check")
            return False
        
        position_id = position["id"]
        
        # Handle datetime parsing more robustly
        entry_time_raw = position.get("entry_time")
        if isinstance(entry_time_raw, str):
            # Parse ISO format datetime string
            try:
                entry_time = datetime.fromisoformat(entry_time_raw.replace('Z', '+00:00'))
            except:
                # Fallback parsing
                entry_time = datetime.strptime(entry_time_raw.split('.')[0], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        else:
            entry_time = entry_time_raw
            # Ensure timezone awareness
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
        
        current_time = datetime.now(timezone.utc)
        position_age_minutes = (current_time - entry_time).total_seconds() / 60
        
        should_close = False
        close_reason = ""
        
        # Log config being used for transparency
        max_time = config.get("max_position_time_minutes", 90)
        stop_loss = config.get("stop_loss_percent", 50)
        
        logger.info(f"🕐 Position {position.get('token_symbol')} age: {position_age_minutes:.1f}min (max: {max_time}min, stop_loss: {stop_loss}%)")
        
        # 1. Time-based exit check (PRIORITY: Apply current config to ALL positions)
        if position_age_minutes >= max_time:
            should_close = True
            close_reason = f"Time limit reached (config: {max_time}min, actual: {position_age_minutes:.1f}min)"
            logger.info(f"⏰ Position {position.get('token_symbol')} auto-closing: {close_reason}")
        
        # 2. Stop loss check (use current config)
        if stop_loss > 0 and unrealized_pnl_percent <= -stop_loss:
            should_close = True
            close_reason = f"Stop loss triggered (config: -{stop_loss}%, actual: {unrealized_pnl_percent:.1f}%)"
            logger.info(f"🛑 Position {position.get('token_symbol')} auto-closing: {close_reason}")
        
        # 3. Take profit checks (use current config)
        take_profit_targets = config.get("take_profit_targets", [])
        take_profit_percentages = config.get("take_profit_percentages", [])
        
        for i, target_multiplier in enumerate(take_profit_targets):
            if target_multiplier <= 1:  # Skip invalid targets
                continue
                
            target_percent = (target_multiplier - 1) * 100  # Convert 2x to 100%, 4x to 300%
            if unrealized_pnl_percent >= target_percent:
                # Calculate how much to sell (use percentage from config)
                sell_percentage = take_profit_percentages[i] if i < len(take_profit_percentages) else 100
                
                # Record which TP level was hit
                current_tps_hit = position.get("take_profits_hit", [])
                if target_multiplier not in current_tps_hit:
                    current_tps_hit.append(target_multiplier)
                    await db.positions.update_one(
                        {"id": position_id},
                        {"$set": {"take_profits_hit": current_tps_hit}}
                    )
                
                should_close = True
                close_reason = f"Take profit {target_multiplier}x reached (+{target_percent:.1f}%, actual: +{unrealized_pnl_percent:.1f}%) - Selling {sell_percentage}%"
                logger.info(f"💰 Position {position.get('token_symbol')} auto-closing: {close_reason}")
                break
        
        if should_close:
            # Auto-close the position using current config
            await auto_close_position(position_id, close_reason, current_price)
            return True
        
        return False
            
    except Exception as e:
        logger.error(f"Error in auto-close check for position {position.get('id')}: {e}")
        return False

async def auto_close_position(position_id: str, reason: str, current_price: float):
    """Automatically close a position and return funds to wallet"""
    try:
        position = await db.positions.find_one({"id": position_id})
        if not position or position.get("status") != "open":
            return
        
        # Calculate final values
        current_value_usd = position.get("current_value_usd", 0)
        entry_amount_usd = position.get("entry_amount_usd", 0)
        realized_pnl = current_value_usd - entry_amount_usd
        
        # Return funds to wallet
        bnb_price = 600  # Approximate BNB price
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
        
        # Update position to closed
        await db.positions.update_one(
            {"id": position_id},
            {
                "$set": {
                    "status": "closed",
                    "exit_time": datetime.now(timezone.utc),
                    "realized_pnl_usd": realized_pnl,
                    "notes": f"Auto-closed: {reason}"
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
                "realized_pnl": realized_pnl
            }
        })
        
        logger.info(f"🔒 AUTO-CLOSED: {position.get('token_symbol')} - {reason} - P&L: ${realized_pnl:.2f}")
        
    except Exception as e:
        logger.error(f"Error auto-closing position {position_id}: {e}")

async def update_position_prices():
    """Update position prices using REAL PancakeSwap data - MILLISECOND UPDATES"""
    logger.info("🚀 Starting REAL PANCAKESWAP price updates (NO SIMULATION!)")
    
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
                        # Add to broadcast list with realistic data
                        updated_positions.append({
                            "id": position["id"],
                            "token_symbol": position.get("token_symbol", ""),
                            "current_price": new_price_usd,
                            "current_value_usd": new_value_usd,
                            "unrealized_pnl_usd": unrealized_pnl_usd,
                            "unrealized_pnl_percent": unrealized_pnl_percent,
                            "price_source": "Realistic Demo Simulation"
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
            
            # Update every 500ms for REAL-TIME millisecond accuracy
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error updating REAL prices: {e}")
            await asyncio.sleep(1)

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
        
        # Get active wallet with real private key
        wallets = await db.wallets.find({"is_active": True, "balance_bnb": {"$gt": 0.01}}).to_list(10)
        if not wallets:
            logger.warning("No wallets with sufficient balance for real trading")
            return
            
        # Select wallet for trading
        import random
        wallet = random.choice(wallets)
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
        
        # Calculate trade amount
        trade_amount_usd = config.get('trade_amount_usd', 50)
        bnb_price_usd = 600  # Approximate BNB price
        trade_amount_bnb = trade_amount_usd / bnb_price_usd
        
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
            # Create REAL position with actual transaction hash
            real_position = Position(
                wallet_id=wallet['id'],
                token_address=detected_pair.token_address,
                token_symbol=detected_pair.token_symbol,
                token_name=detected_pair.token_name,
                pair_address=detected_pair.pair_address,
                entry_amount_bnb=trade_amount_bnb,
                entry_amount_usd=trade_amount_usd,
                entry_price=0.0,  # Will be calculated from actual transaction
                current_price=0.0,
                current_value_usd=trade_amount_usd,
                tokens_held=0.0,  # Will be calculated from transaction receipt
                entry_time=datetime.now(timezone.utc),
                status="open",
                unrealized_pnl_usd=0.0,
                unrealized_pnl_percent=0.0,
                entry_tx_hash=tx_hash  # REAL transaction hash!
            )
            
            # Store position
            await db.positions.insert_one(real_position.dict())
            
            # Broadcast real position
            await bot_state.broadcast_to_clients({
                "type": "real_position_created",
                "data": real_position.dict()
            })
            
            logger.info(f"🚀 REAL TRADE EXECUTED: {detected_pair.token_symbol} - TX: {tx_hash}")
        
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
        
        # Sign transaction with real private key
        signed_txn = w3.eth.account.sign_transaction(transaction, account.key)
        
        # SEND REAL TRANSACTION TO BLOCKCHAIN
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
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
            
            # Sign and send approval
            signed_approve = w3.eth.account.sign_transaction(approve_tx, account.key)
            approve_hash = w3.eth.send_raw_transaction(signed_approve.rawTransaction)
            
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
        
        # Sign and send real sell transaction
        signed_txn = w3.eth.account.sign_transaction(transaction, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()
        
        logger.info(f"💰 REAL SELL SENT: {tx_hash_hex}")
        logger.info(f"🔗 View on BSCScan: https://bscscan.com/tx/{tx_hash_hex}")
        
        return tx_hash_hex
        
    except Exception as e:
        logger.error(f"REAL sell transaction failed: {e}")
        return None
    """Execute a demo trade for a real detected token"""
    try:
        # Get trading configuration
        config = await db.trading_config.find_one({"is_active": True})
        if not config:
            logger.warning("No trading config found for demo execution")
            return
            
        # Get active demo wallets with balance
        wallets = await db.wallets.find({"is_active": True, "balance_bnb": {"$gt": 0.1}}).to_list(10)
        if not wallets:
            logger.warning("No demo wallets with sufficient balance for trading")
            return
            
        # Select a random wallet for demo trading
        import random
        wallet = random.choice(wallets)
        
        # Get REAL entry price from DexScreener (matches the links exactly!)
        real_price_data = await get_real_time_token_price(detected_pair.token_address)
        
        if real_price_data and real_price_data['price_usd'] > 0:
            entry_price_usd = real_price_data['price_usd']
            logger.info(f"📊 REAL ENTRY PRICE: {detected_pair.token_symbol} = ${entry_price_usd:.8f} (DexScreener)")
        else:
            # Fallback to REAL PancakeSwap calculation (not simulation!)
            entry_price_usd = detected_pair.initial_price
            if entry_price_usd <= 0:
                logger.warning(f"Invalid real price for {detected_pair.token_symbol} - skipping trade")
                return
            logger.info(f"📊 REAL ENTRY PRICE: {detected_pair.token_symbol} = ${entry_price_usd:.8f} (PancakeSwap)")
        
        # Calculate trade size based on current config
        trade_amount_usd = config.get('trade_amount_usd', 50)
        bnb_price = 320.0  # Approximate BNB price for demo
        trade_amount_bnb = trade_amount_usd / bnb_price
        
        # Check if wallet has enough balance
        if wallet['balance_bnb'] < trade_amount_bnb:
            logger.warning(f"Wallet {wallet.get('name')} insufficient balance for ${trade_amount_usd} trade")
            return
            
        # Calculate REAL tokens purchased based on REAL market price
        tokens_purchased = trade_amount_usd / entry_price_usd
        
        logger.info(f"💰 REAL TRADE: {detected_pair.token_symbol} - ${trade_amount_usd} ÷ ${entry_price_usd:.8f} = {tokens_purchased:.2f} tokens")
            
        # Create position with REAL market data (matches DexScreener links)
        demo_position = Position(
            wallet_id=wallet['id'],
            token_address=detected_pair.token_address,
            token_symbol=detected_pair.token_symbol,
            token_name=detected_pair.token_name,
            pair_address=detected_pair.pair_address,
            entry_amount_bnb=trade_amount_bnb,
            entry_amount_usd=trade_amount_usd,
            entry_price=entry_price_usd,  # REAL market price
            current_price=entry_price_usd,  # Start with REAL price
            current_value_usd=trade_amount_usd,  # Current value
            tokens_held=tokens_purchased,  # REAL token count
            entry_time=datetime.now(timezone.utc),
            status="open",
            unrealized_pnl_usd=0.0,  # Starts at zero
            unrealized_pnl_percent=0.0,  # Starts at zero
            entry_tx_hash=f"demo_tx_{detected_pair.id[:8]}"
        )
        
        # Update wallet balance (deduct used funds)
        new_wallet_balance = wallet['balance_bnb'] - trade_amount_bnb
        await db.wallets.update_one(
            {"id": wallet['id']},
            {"$set": {"balance_bnb": max(0, new_wallet_balance)}}
        )
        
        # Store position in database
        await db.positions.insert_one(demo_position.dict())
        
        # Update detected pair to mark as bought
        await db.detected_pairs.update_one(
            {"id": detected_pair.id},
            {"$set": {"action_taken": "bought"}}
        )
        
        # Broadcast position creation
        await bot_state.broadcast_to_clients({
            "type": "demo_position_created",
            "data": demo_position.dict()
        })
        
        logger.info(f"💰 DEMO TRADE EXECUTED: {detected_pair.token_symbol} - ${trade_amount_usd} using wallet {wallet.get('name')}")
        
    except Exception as e:
        logger.error(f"Error executing demo trade for {detected_pair.token_symbol}: {e}")

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
                
                # Execute demo trade with real token data
                await execute_demo_trade_for_real_token(new_pair)
                
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

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Paradox Bot API shutting down...")
    bot_state.is_running = False
    client.close()