from fastapi import FastAPI, APIRouter, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import json
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
app = FastAPI(title="PCS Sniper Bot API", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# ==================== BLOCKCHAIN CONFIG ====================

class BlockchainConfig:
    def __init__(self):
        self.bsc_rpc_http = os.getenv('BSC_RPC_HTTP')
        self.bsc_rpc_ws = os.getenv('BSC_RPC_WS')
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
    return {"message": "PCS Sniper Bot API", "version": "1.0.0", "status": "active"}

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
    background_tasks.add_task(start_pair_monitoring)
    
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
async def get_positions():
    positions = await db.positions.find().sort("entry_time", -1).to_list(100)
    return [Position(**pos) for pos in positions]

@api_router.get("/pairs/detected", response_model=List[NewPairEvent])
async def get_detected_pairs():
    pairs = await db.detected_pairs.find().sort("detected_at", -1).limit(50).to_list(50)
    return [NewPairEvent(**pair) for pair in pairs]

@api_router.get("/stats", response_model=TradingStats)
async def get_trading_stats():
    stats = await db.trading_stats.find_one({}) or TradingStats().dict()
    return TradingStats(**stats)

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
        # Update position status to closed
        await db.positions.update_one(
            {"id": position_id},
            {
                "$set": {
                    "status": "closed",
                    "exit_time": datetime.now(timezone.utc).isoformat(),
                    "realized_pnl_usd": position.get("unrealized_pnl_usd", 0),
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
                "realized_pnl": position.get("unrealized_pnl_usd", 0)
            }
        })
        
        logger.info(f"Position closed manually: {position.get('token_symbol')} - PnL: ${position.get('unrealized_pnl_usd', 0):.2f}")
        
        return {
            "message": "Position closed successfully",
            "position_id": position_id,
            "realized_pnl": position.get("unrealized_pnl_usd", 0)
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
    
    for position in open_positions:
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
    logger.info("Starting pair monitoring...")
    
    while bot_state.is_running:
        try:
            # Simulate pair detection (replace with real WebSocket monitoring)
            await simulate_pair_detection()
            await asyncio.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"Error in pair monitoring: {e}")
            await asyncio.sleep(10)

async def create_demo_position():
    """Create a demo trading position for testing"""
    import random
    
    # Get active wallets
    wallets = await db.wallets.find({"is_active": True, "balance_bnb": {"$gt": 0}}).to_list(10)
    if not wallets:
        return
    
    # Pick a random wallet
    wallet = random.choice(wallets)
    
    # Create demo position with random data
    demo_position = Position(
        wallet_id=wallet["id"],
        token_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
        token_symbol=f"DEMO{random.randint(1, 9999)}",
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
    
    # Store in database
    await db.positions.insert_one(demo_position.dict())
    
    # Broadcast to connected clients
    await bot_state.broadcast_to_clients({
        "type": "demo_position_created",
        "data": demo_position.dict()
    })
    
    logger.info(f"Demo position created: {demo_position.token_symbol} - {demo_position.unrealized_pnl_percent:.2f}% P&L")

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
    logger.info("PCS Sniper Bot API starting up...")
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
    logger.info("PCS Sniper Bot API shutting down...")
    bot_state.is_running = False
    client.close()