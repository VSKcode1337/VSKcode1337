#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Paradox Bot
Tests all critical backend functionality for live trading readiness
"""

import asyncio
import aiohttp
import json
import websockets
import os
import sys
from datetime import datetime, timezone
import uuid
import time

# Backend URL from environment
BACKEND_URL = "https://paradox-bot.preview.emergentagent.com/api"
WS_URL = "wss://paradox-bot.preview.emergentagent.com/ws"

class ParadoxBotTester:
    def __init__(self):
        self.session = None
        self.test_results = {
            "api_endpoints": {},
            "database_connectivity": {},
            "websocket_communication": {},
            "bot_control": {},
            "external_integrations": {},
            "overall_status": "UNKNOWN"
        }
        self.test_wallet_id = None
        self.test_position_id = None
        
    async def setup(self):
        """Initialize test session"""
        self.session = aiohttp.ClientSession()
        print("🔧 Test session initialized")
        
    async def cleanup(self):
        """Cleanup test session"""
        if self.session:
            await self.session.close()
        print("🧹 Test session cleaned up")
        
    async def test_api_endpoints(self):
        """Test all critical API endpoints"""
        print("\n🔍 Testing API Endpoints...")
        
        endpoints_to_test = [
            ("GET", "/", "Root endpoint"),
            ("GET", "/status", "Bot status"),
            ("GET", "/config/trading", "Trading config"),
            ("GET", "/config/rpc", "RPC config"),
            ("GET", "/wallets", "Wallets list"),
            ("GET", "/positions", "Positions list"),
            ("GET", "/pairs/detected", "Detected pairs"),
            ("GET", "/stats", "Trading stats")
        ]
        
        for method, endpoint, description in endpoints_to_test:
            try:
                url = f"{BACKEND_URL}{endpoint}"
                async with self.session.request(method, url) as response:
                    status = response.status
                    data = await response.json()
                    
                    if status == 200:
                        self.test_results["api_endpoints"][endpoint] = {
                            "status": "PASS",
                            "response_code": status,
                            "description": description
                        }
                        print(f"  ✅ {description}: {status}")
                    else:
                        self.test_results["api_endpoints"][endpoint] = {
                            "status": "FAIL",
                            "response_code": status,
                            "description": description,
                            "error": data
                        }
                        print(f"  ❌ {description}: {status} - {data}")
                        
            except Exception as e:
                self.test_results["api_endpoints"][endpoint] = {
                    "status": "ERROR",
                    "description": description,
                    "error": str(e)
                }
                print(f"  ❌ {description}: ERROR - {str(e)}")
                
    async def test_database_connectivity(self):
        """Test database operations"""
        print("\n🗄️ Testing Database Connectivity...")
        
        # Test wallet creation (database write)
        try:
            wallet_data = {
                "name": "Test Wallet",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234"
            }
            
            async with self.session.post(f"{BACKEND_URL}/wallets", json=wallet_data) as response:
                if response.status == 200:
                    wallet_response = await response.json()
                    self.test_wallet_id = wallet_response.get("id")
                    self.test_results["database_connectivity"]["wallet_creation"] = {
                        "status": "PASS",
                        "description": "Wallet creation (DB write)"
                    }
                    print("  ✅ Wallet creation (DB write): PASS")
                else:
                    error_data = await response.json()
                    self.test_results["database_connectivity"]["wallet_creation"] = {
                        "status": "FAIL",
                        "description": "Wallet creation (DB write)",
                        "error": error_data
                    }
                    print(f"  ❌ Wallet creation (DB write): FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["database_connectivity"]["wallet_creation"] = {
                "status": "ERROR",
                "description": "Wallet creation (DB write)",
                "error": str(e)
            }
            print(f"  ❌ Wallet creation (DB write): ERROR - {str(e)}")
            
        # Test trading config update (database persistence)
        try:
            config_data = {
                "trade_amount_usd": 50.0,
                "max_trade_amount_usd": 100.0,
                "min_liquidity_usd": 10000.0,
                "max_tax_buy_percent": 6.0,
                "max_tax_sell_percent": 6.0,
                "take_profit_targets": [10, 20, 30],
                "take_profit_percentages": [50.0, 30.0, 20.0],
                "stop_loss_percent": 50.0,
                "max_position_time_minutes": 90,
                "slippage_tolerance_percent": 12.0,
                "is_active": True
            }
            
            async with self.session.post(f"{BACKEND_URL}/config/trading", json=config_data) as response:
                if response.status == 200:
                    self.test_results["database_connectivity"]["config_persistence"] = {
                        "status": "PASS",
                        "description": "Trading config persistence"
                    }
                    print("  ✅ Trading config persistence: PASS")
                else:
                    error_data = await response.json()
                    self.test_results["database_connectivity"]["config_persistence"] = {
                        "status": "FAIL",
                        "description": "Trading config persistence",
                        "error": error_data
                    }
                    print(f"  ❌ Trading config persistence: FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["database_connectivity"]["config_persistence"] = {
                "status": "ERROR",
                "description": "Trading config persistence",
                "error": str(e)
            }
            print(f"  ❌ Trading config persistence: ERROR - {str(e)}")
            
    async def test_websocket_communication(self):
        """Test WebSocket connectivity and real-time updates"""
        print("\n🔌 Testing WebSocket Communication...")
        
        try:
            async with websockets.connect(WS_URL) as websocket:
                # Test connection establishment
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                
                if data.get("type") == "connection_established":
                    self.test_results["websocket_communication"]["connection"] = {
                        "status": "PASS",
                        "description": "WebSocket connection establishment"
                    }
                    print("  ✅ WebSocket connection establishment: PASS")
                    
                    # Test ping-pong
                    ping_message = {"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}
                    await websocket.send(json.dumps(ping_message))
                    
                    pong_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    pong_data = json.loads(pong_response)
                    
                    if pong_data.get("type") == "pong":
                        self.test_results["websocket_communication"]["ping_pong"] = {
                            "status": "PASS",
                            "description": "WebSocket ping-pong"
                        }
                        print("  ✅ WebSocket ping-pong: PASS")
                    else:
                        self.test_results["websocket_communication"]["ping_pong"] = {
                            "status": "FAIL",
                            "description": "WebSocket ping-pong",
                            "error": "No pong response received"
                        }
                        print("  ❌ WebSocket ping-pong: FAIL - No pong response")
                        
                else:
                    self.test_results["websocket_communication"]["connection"] = {
                        "status": "FAIL",
                        "description": "WebSocket connection establishment",
                        "error": "Unexpected initial message"
                    }
                    print(f"  ❌ WebSocket connection establishment: FAIL - Unexpected message: {data}")
                    
        except asyncio.TimeoutError:
            self.test_results["websocket_communication"]["connection"] = {
                "status": "FAIL",
                "description": "WebSocket connection establishment",
                "error": "Connection timeout"
            }
            print("  ❌ WebSocket connection establishment: FAIL - Timeout")
        except Exception as e:
            self.test_results["websocket_communication"]["connection"] = {
                "status": "ERROR",
                "description": "WebSocket connection establishment",
                "error": str(e)
            }
            print(f"  ❌ WebSocket connection establishment: ERROR - {str(e)}")
            
    async def test_bot_control_functions(self):
        """Test bot start/stop functionality"""
        print("\n🤖 Testing Bot Control Functions...")
        
        # Test bot start
        try:
            async with self.session.post(f"{BACKEND_URL}/sniper/start") as response:
                if response.status == 200:
                    start_data = await response.json()
                    self.test_results["bot_control"]["start"] = {
                        "status": "PASS",
                        "description": "Bot start functionality"
                    }
                    print("  ✅ Bot start functionality: PASS")
                    
                    # Wait a moment then test status
                    await asyncio.sleep(2)
                    
                    # Check if bot is running
                    async with self.session.get(f"{BACKEND_URL}/status") as status_response:
                        if status_response.status == 200:
                            status_data = await status_response.json()
                            if status_data.get("is_running"):
                                self.test_results["bot_control"]["status_tracking"] = {
                                    "status": "PASS",
                                    "description": "Bot status tracking"
                                }
                                print("  ✅ Bot status tracking: PASS")
                            else:
                                self.test_results["bot_control"]["status_tracking"] = {
                                    "status": "FAIL",
                                    "description": "Bot status tracking",
                                    "error": "Bot not showing as running after start"
                                }
                                print("  ❌ Bot status tracking: FAIL - Not running after start")
                        
                else:
                    error_data = await response.json()
                    self.test_results["bot_control"]["start"] = {
                        "status": "FAIL",
                        "description": "Bot start functionality",
                        "error": error_data
                    }
                    print(f"  ❌ Bot start functionality: FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["bot_control"]["start"] = {
                "status": "ERROR",
                "description": "Bot start functionality",
                "error": str(e)
            }
            print(f"  ❌ Bot start functionality: ERROR - {str(e)}")
            
        # Test bot stop
        try:
            async with self.session.post(f"{BACKEND_URL}/sniper/stop") as response:
                if response.status == 200:
                    self.test_results["bot_control"]["stop"] = {
                        "status": "PASS",
                        "description": "Bot stop functionality"
                    }
                    print("  ✅ Bot stop functionality: PASS")
                else:
                    error_data = await response.json()
                    self.test_results["bot_control"]["stop"] = {
                        "status": "FAIL",
                        "description": "Bot stop functionality",
                        "error": error_data
                    }
                    print(f"  ❌ Bot stop functionality: FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["bot_control"]["stop"] = {
                "status": "ERROR",
                "description": "Bot stop functionality",
                "error": str(e)
            }
            print(f"  ❌ Bot stop functionality: ERROR - {str(e)}")
            
    async def test_external_integrations(self):
        """Test external service integrations"""
        print("\n🌐 Testing External Service Integrations...")
        
        # Test blockchain connectivity through status endpoint
        try:
            async with self.session.get(f"{BACKEND_URL}/status") as response:
                if response.status == 200:
                    status_data = await response.json()
                    blockchain_connected = status_data.get("blockchain_connected", False)
                    last_block = status_data.get("last_block")
                    
                    if blockchain_connected and last_block:
                        self.test_results["external_integrations"]["blockchain_rpc"] = {
                            "status": "PASS",
                            "description": "BSC RPC connectivity",
                            "last_block": last_block
                        }
                        print(f"  ✅ BSC RPC connectivity: PASS (Block: {last_block})")
                    else:
                        self.test_results["external_integrations"]["blockchain_rpc"] = {
                            "status": "FAIL",
                            "description": "BSC RPC connectivity",
                            "error": "Not connected or no block data"
                        }
                        print("  ❌ BSC RPC connectivity: FAIL - Not connected")
                        
        except Exception as e:
            self.test_results["external_integrations"]["blockchain_rpc"] = {
                "status": "ERROR",
                "description": "BSC RPC connectivity",
                "error": str(e)
            }
            print(f"  ❌ BSC RPC connectivity: ERROR - {str(e)}")
            
        # Test RPC configuration
        try:
            async with self.session.get(f"{BACKEND_URL}/config/rpc") as response:
                if response.status == 200:
                    rpc_config = await response.json()
                    if rpc_config.get("bsc_rpc_http"):
                        self.test_results["external_integrations"]["rpc_config"] = {
                            "status": "PASS",
                            "description": "RPC configuration"
                        }
                        print("  ✅ RPC configuration: PASS")
                    else:
                        self.test_results["external_integrations"]["rpc_config"] = {
                            "status": "FAIL",
                            "description": "RPC configuration",
                            "error": "No RPC HTTP endpoint configured"
                        }
                        print("  ❌ RPC configuration: FAIL - No HTTP endpoint")
                        
        except Exception as e:
            self.test_results["external_integrations"]["rpc_config"] = {
                "status": "ERROR",
                "description": "RPC configuration",
                "error": str(e)
            }
            print(f"  ❌ RPC configuration: ERROR - {str(e)}")
            
    async def test_pair_detection_readiness(self):
        """Test if pair detection system is ready"""
        print("\n🔍 Testing Pair Detection Readiness...")
        
        # Check detected pairs endpoint
        try:
            async with self.session.get(f"{BACKEND_URL}/pairs/detected") as response:
                if response.status == 200:
                    pairs_data = await response.json()
                    self.test_results["external_integrations"]["pair_detection"] = {
                        "status": "PASS",
                        "description": "Pair detection endpoint",
                        "pairs_count": len(pairs_data)
                    }
                    print(f"  ✅ Pair detection endpoint: PASS ({len(pairs_data)} pairs)")
                else:
                    error_data = await response.json()
                    self.test_results["external_integrations"]["pair_detection"] = {
                        "status": "FAIL",
                        "description": "Pair detection endpoint",
                        "error": error_data
                    }
                    print(f"  ❌ Pair detection endpoint: FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["external_integrations"]["pair_detection"] = {
                "status": "ERROR",
                "description": "Pair detection endpoint",
                "error": str(e)
            }
            print(f"  ❌ Pair detection endpoint: ERROR - {str(e)}")
            
    async def test_position_management(self):
        """Test position management functionality"""
        print("\n📊 Testing Position Management...")
        
        # Test positions endpoint
        try:
            async with self.session.get(f"{BACKEND_URL}/positions") as response:
                if response.status == 200:
                    positions_data = await response.json()
                    self.test_results["api_endpoints"]["positions_management"] = {
                        "status": "PASS",
                        "description": "Position management endpoint",
                        "positions_count": len(positions_data)
                    }
                    print(f"  ✅ Position management endpoint: PASS ({len(positions_data)} positions)")
                    
                    # If there are positions, test close functionality
                    if positions_data:
                        test_position = positions_data[0]
                        position_id = test_position.get("id")
                        
                        if test_position.get("status") in ["open", "partial"]:
                            # Test position closing
                            async with self.session.post(f"{BACKEND_URL}/positions/{position_id}/close") as close_response:
                                if close_response.status == 200:
                                    self.test_results["api_endpoints"]["position_closing"] = {
                                        "status": "PASS",
                                        "description": "Position closing functionality"
                                    }
                                    print("  ✅ Position closing functionality: PASS")
                                else:
                                    close_error = await close_response.json()
                                    self.test_results["api_endpoints"]["position_closing"] = {
                                        "status": "FAIL",
                                        "description": "Position closing functionality",
                                        "error": close_error
                                    }
                                    print(f"  ❌ Position closing functionality: FAIL - {close_error}")
                        
                else:
                    error_data = await response.json()
                    self.test_results["api_endpoints"]["positions_management"] = {
                        "status": "FAIL",
                        "description": "Position management endpoint",
                        "error": error_data
                    }
                    print(f"  ❌ Position management endpoint: FAIL - {error_data}")
                    
        except Exception as e:
            self.test_results["api_endpoints"]["positions_management"] = {
                "status": "ERROR",
                "description": "Position management endpoint",
                "error": str(e)
            }
            print(f"  ❌ Position management endpoint: ERROR - {str(e)}")
            
    async def cleanup_test_data(self):
        """Clean up test data created during testing"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete test wallet if created
        if self.test_wallet_id:
            try:
                async with self.session.delete(f"{BACKEND_URL}/wallets/{self.test_wallet_id}") as response:
                    if response.status == 200:
                        print("  ✅ Test wallet cleaned up")
                    else:
                        print("  ⚠️ Could not clean up test wallet")
            except Exception as e:
                print(f"  ⚠️ Error cleaning up test wallet: {str(e)}")
                
    def generate_summary(self):
        """Generate test summary"""
        print("\n" + "="*60)
        print("🎯 PARADOX BOT BACKEND TEST SUMMARY")
        print("="*60)
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        
        for category, tests in self.test_results.items():
            if category == "overall_status":
                continue
                
            print(f"\n📋 {category.upper().replace('_', ' ')}:")
            for test_name, result in tests.items():
                total_tests += 1
                status = result.get("status", "UNKNOWN")
                description = result.get("description", test_name)
                
                if status == "PASS":
                    passed_tests += 1
                    print(f"  ✅ {description}")
                elif status == "FAIL":
                    failed_tests += 1
                    error = result.get("error", "Unknown error")
                    print(f"  ❌ {description} - {error}")
                elif status == "ERROR":
                    error_tests += 1
                    error = result.get("error", "Unknown error")
                    print(f"  🔥 {description} - {error}")
                    
        print(f"\n📊 OVERALL RESULTS:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests} ✅")
        print(f"  Failed: {failed_tests} ❌")
        print(f"  Errors: {error_tests} 🔥")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"  Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            self.test_results["overall_status"] = "READY_FOR_LIVE_TRADING"
            print(f"\n🚀 STATUS: READY FOR LIVE TRADING")
        elif success_rate >= 70:
            self.test_results["overall_status"] = "MOSTLY_READY_MINOR_ISSUES"
            print(f"\n⚠️ STATUS: MOSTLY READY - MINOR ISSUES TO RESOLVE")
        else:
            self.test_results["overall_status"] = "NOT_READY_CRITICAL_ISSUES"
            print(f"\n🚨 STATUS: NOT READY - CRITICAL ISSUES FOUND")
            
        print("="*60)
        
        return self.test_results

async def main():
    """Main test execution"""
    print("🚀 Starting Paradox Bot Backend Comprehensive Testing")
    print("="*60)
    
    tester = ParadoxBotTester()
    
    try:
        await tester.setup()
        
        # Run all tests
        await tester.test_api_endpoints()
        await tester.test_database_connectivity()
        await tester.test_websocket_communication()
        await tester.test_bot_control_functions()
        await tester.test_external_integrations()
        await tester.test_pair_detection_readiness()
        await tester.test_position_management()
        
        # Clean up test data
        await tester.cleanup_test_data()
        
        # Generate summary
        results = tester.generate_summary()
        
        return results
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    results = asyncio.run(main())