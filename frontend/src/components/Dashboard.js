import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Progress } from './ui/progress';
import { Zap, TrendingUp, Target, Wallet, Activity, AlertTriangle, Clock, DollarSign } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ botStatus, isConnected, ws }) => {
  const [positions, setPositions] = useState([]);
  const [detectedPairs, setDetectedPairs] = useState([]);
  const [stats, setStats] = useState({
    total_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    total_pnl_usd: 0,
    win_rate_percent: 0,
    pairs_detected: 0,
    pairs_traded: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Refresh when botStatus updates (including position changes)
  useEffect(() => {
    if (botStatus.last_updated) {
      fetchDashboardData();
    }
  }, [botStatus.last_updated]);

  useEffect(() => {
    if (ws) {
      const handleMessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'new_pair_detected') {
          setDetectedPairs(prev => [message.data, ...prev.slice(0, 19)]);
          toast.success(`New pair detected: ${message.data.token_symbol}`, {
            description: `Liquidity: $${message.data.liquidity_usd?.toLocaleString()}`
          });
        }
      };
      
      ws.addEventListener('message', handleMessage);
      return () => ws.removeEventListener('message', handleMessage);
    }
  }, [ws]);

  const fetchDashboardData = async () => {
    try {
      const [positionsRes, pairsRes, statsRes, walletsRes] = await Promise.all([
        axios.get(`${API}/positions`),
        axios.get(`${API}/pairs/detected`),
        axios.get(`${API}/stats`),
        axios.get(`${API}/wallets`)
      ]);
      
      const allPositions = positionsRes.data;
      const wallets = walletsRes.data;
      const detectedPairs = pairsRes.data;
      
      // Add wallet names to positions
      const positionsWithWallets = allPositions.map(position => {
        const wallet = wallets.find(w => w.id === position.wallet_id);
        return {
          ...position,
          wallet_name: wallet ? wallet.name : 'Unknown Wallet'
        };
      });
      
      const openPositions = positionsWithWallets.filter(p => p.status === 'open');
      const closedPositions = positionsWithWallets.filter(p => p.status === 'closed');
      
      // Calculate REALIZED PnL (from closed positions only)
      const realizedPnL = closedPositions.reduce((sum, p) => sum + (p.realized_pnl_usd || p.unrealized_pnl_usd || 0), 0);
      
      // Calculate UNREALIZED PnL (from open positions only)  
      const unrealizedPnL = openPositions.reduce((sum, p) => sum + (p.unrealized_pnl_usd || 0), 0);
      
      // Calculate TOTAL PnL (realized + unrealized)
      const totalPnL = realizedPnL + unrealizedPnL;
      
      const winningTrades = closedPositions.filter(p => (p.realized_pnl_usd || p.unrealized_pnl_usd || 0) > 0).length;
      const totalTrades = closedPositions.length;
      const winRate = totalTrades > 0 ? (winningTrades / totalTrades) * 100 : 0;
      
      // Update stats with calculated values
      const calculatedStats = {
        ...statsRes.data,
        total_pnl_usd: totalPnL,
        realized_pnl_usd: realizedPnL,
        unrealized_pnl_usd: unrealizedPnL,
        winning_trades: winningTrades,
        losing_trades: totalTrades - winningTrades,
        total_trades: totalTrades,
        win_rate_percent: winRate,
        pairs_detected: detectedPairs.length,  // Sync with actual detected pairs
        pairs_traded: totalTrades
      };
      
      setPositions(positionsWithWallets);
      setDetectedPairs(pairsRes.data);
      setStats(calculatedStats);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const startSniper = async () => {
    try {
      await axios.post(`${API}/sniper/start`);
      toast.success('Sniper bot started successfully!');
    } catch (error) {
      toast.error('Failed to start sniper bot');
    }
  };

  const stopSniper = async () => {
    try {
      await axios.post(`${API}/sniper/stop`);
      toast.success('Sniper bot stopped');
    } catch (error) {
      toast.error('Failed to stop sniper bot');
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };

  const formatPnL = (pnl, isPercent = false) => {
    const value = isPercent ? `${pnl.toFixed(2)}%` : formatCurrency(pnl);
    const colorClass = pnl >= 0 ? 'text-green-400' : 'text-red-400';
    const prefix = pnl > 0 ? '+' : '';
    return <span className={colorClass}>{prefix}{value}</span>;
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="glass animate-pulse">
            <CardHeader className="pb-2">
              <div className="h-4 bg-gray-600 rounded w-3/4"></div>
            </CardHeader>
            <CardContent>
              <div className="h-8 bg-gray-600 rounded w-1/2"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="glass card-hover border-blue-500/20">
          <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium text-gray-300">Total P&L</CardTitle>
            <TrendingUp className="h-4 w-4 text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">
              {formatPnL(stats.total_pnl_usd)}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {stats.total_trades} total trades
            </p>
          </CardContent>
        </Card>

        <Card className="glass card-hover border-green-500/20">
          <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium text-gray-300">Win Rate</CardTitle>
            <Target className="h-4 w-4 text-green-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">
              {(stats.win_rate_percent || 0).toFixed(1)}%
            </div>
            <Progress 
              value={stats.win_rate_percent} 
              className="mt-2 h-2" 
            />
            <p className="text-xs text-gray-400 mt-1">
              {stats.winning_trades}W / {stats.losing_trades}L
            </p>
          </CardContent>
        </Card>

        <Card className="glass card-hover border-purple-500/20">
          <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium text-gray-300">Active Positions</CardTitle>
            <Wallet className="h-4 w-4 text-purple-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">
              {positions.filter(p => p.status === 'open').length}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {formatCurrency(positions.reduce((sum, p) => sum + (p.status === 'open' ? p.current_value_usd : 0), 0))} value
            </p>
          </CardContent>
        </Card>

        <Card className="glass card-hover border-yellow-500/20">
          <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm font-medium text-gray-300">Pairs Detected</CardTitle>
            <Activity className="h-4 w-4 text-yellow-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-white">
              {stats.pairs_detected}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {stats.pairs_traded || 0} traded ({(((stats.pairs_traded || 0) / Math.max((stats.pairs_detected || 1), 1)) * 100).toFixed(1)}%)
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Control Panel */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl text-white flex items-center gap-2">
                <Zap className="h-5 w-5 text-blue-400" />
                Sniper Control
              </CardTitle>
              <CardDescription className="text-gray-400">
                Monitor and control your high-frequency trading bot
              </CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${
                  botStatus.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-500'
                }`}></div>
                <span className="text-sm text-gray-300">
                  {botStatus.is_running ? 'ACTIVE' : 'STOPPED'}
                </span>
              </div>
              
              {botStatus.is_running ? (
                <Button 
                  onClick={stopSniper}
                  variant="destructive"
                  className="btn-danger"
                  data-testid="stop-sniper-btn"
                >
                  Stop Sniper
                </Button>
              ) : (
                <Button 
                  onClick={startSniper}
                  className="btn-success"
                  data-testid="start-sniper-btn"
                >
                  Start Sniper
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span className="text-sm text-gray-300">WebSocket</span>
            </div>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                botStatus.blockchain_connected ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span className="text-sm text-gray-300">Blockchain</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Block:</span>
              <span className="text-sm text-white font-mono">
                {botStatus.last_block?.toLocaleString() || 'N/A'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Clients:</span>
              <span className="text-sm text-white">
                {botStatus.connected_clients}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Tabs */}
      <Tabs defaultValue="live-feed" className="space-y-6">
        <TabsList className="bg-gray-800/50 border border-gray-700">
          <TabsTrigger value="live-feed" className="data-[state=active]:bg-blue-600">Live Feed</TabsTrigger>
          <TabsTrigger value="positions" className="data-[state=active]:bg-blue-600">Positions</TabsTrigger>
          <TabsTrigger value="analytics" className="data-[state=active]:bg-blue-600">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="live-feed">
          <Card className="glass border-gray-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Activity className="h-5 w-5 text-green-400" />
                Live Pair Detection Feed
              </CardTitle>
              <CardDescription className="text-gray-400">
                Real-time new token pair discoveries on PancakeSwap
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {detectedPairs.length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No pairs detected yet. Start the sniper to begin monitoring.</p>
                  </div>
                ) : (
                  detectedPairs.map((pair) => (
                    <div key={pair.id} className="flex items-center justify-between p-4 bg-gray-800/30 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
                      <div className="flex items-center space-x-4">
                        <div className="flex flex-col">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-white">{pair.token_symbol}</span>
                            <Badge variant={pair.risk_passed ? "default" : "destructive"} className="text-xs">
                              {pair.risk_passed ? 'SAFE' : 'RISKY'}
                            </Badge>
                          </div>
                          <span className="text-xs text-gray-400 font-mono">{pair.token_address?.slice(0, 8)}...</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-6 text-sm">
                        <div className="text-center">
                          <div className="text-white font-semibold">${pair.liquidity_usd?.toLocaleString()}</div>
                          <div className="text-gray-400 text-xs">Liquidity</div>
                        </div>
                        <div className="text-center">
                          <div className="text-white font-semibold">{pair.wbnb_reserves?.toFixed(2)} BNB</div>
                          <div className="text-gray-400 text-xs">WBNB Pool</div>
                        </div>
                        <div className="text-center">
                          <div className="text-white font-semibold">
                            {new Date().toLocaleTimeString('en-GB', { 
                              timeZone: 'Europe/London',
                              hour12: false,
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit'
                            })}
                          </div>
                          <div className="text-gray-400 text-xs">Just Now</div>
                        </div>
                        <Badge variant={pair.action_taken === 'bought' ? 'default' : 'secondary'}>
                          {pair.action_taken.toUpperCase()}
                        </Badge>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="positions">
          <Card className="glass border-gray-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Wallet className="h-5 w-5 text-blue-400" />
                Active Positions
              </CardTitle>
              <CardDescription className="text-gray-400">
                Monitor your current trading positions and P&L
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {positions.filter(p => p.status === 'open').length === 0 ? (
                  <div className="text-center py-8 text-gray-400">
                    <Wallet className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>No active positions. Positions will appear here when trades are executed.</p>
                  </div>
                ) : (
                  positions.filter(p => p.status === 'open').map((position) => (
                    <div key={position.id} className="p-4 bg-gray-800/30 rounded-lg border border-gray-700">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-white text-lg">{position.token_symbol}</h3>
                            <Badge variant="outline" className="text-xs">{position.status.toUpperCase()}</Badge>
                          </div>
                          <div className="flex items-center gap-2 text-sm">
                            <span className="text-blue-400 font-medium">👛 {position.wallet_name}</span>
                            <span className="text-gray-500">•</span>
                            <span className="text-gray-400 font-mono text-xs">{position.token_address?.slice(0, 6)}...{position.token_address?.slice(-4)}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold">{formatPnL(position.unrealized_pnl_usd)}</div>
                          <div className="text-sm">{formatPnL(position.unrealized_pnl_percent, true)}</div>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-gray-400">Entry: </span>
                          <span className="text-white">{formatCurrency(position.entry_amount_usd)}</span>
                        </div>
                        <div>
                          <span className="text-gray-400">Current: </span>
                          <span className="text-white">{formatCurrency(position.current_value_usd)}</span>
                        </div>
                        <div>
                          <span className="text-gray-400">Time: </span>
                          <span className="text-white">
                            {Math.floor((new Date() - new Date(position.entry_time)) / 60000)}m
                          </span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analytics">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-green-400" />
                  Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Total Volume</span>
                  <span className="text-white font-semibold">{formatCurrency(stats.total_volume_usd)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Average Hold Time</span>
                  <span className="text-white font-semibold">{(stats.avg_hold_time_minutes || 0).toFixed(1)}m</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Win Rate</span>
                  <span className="text-white font-semibold">{(stats.win_rate_percent || 0).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">Detection Rate</span>
                  <span className="text-white font-semibold">
                    {(((stats.pairs_traded || 0) / Math.max((stats.pairs_detected || 1), 1)) * 100).toFixed(1)}%
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Clock className="h-5 w-5 text-yellow-400" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {positions.slice(0, 5).map((position, index) => (
                    <div key={position.id} className="flex items-center justify-between py-2 border-b border-gray-700 last:border-b-0">
                      <div>
                        <div className="text-white text-sm font-medium">{position.token_symbol}</div>
                        <div className="text-gray-400 text-xs">
                          👛 {position.wallet_name} • {new Date(position.entry_time).toLocaleTimeString('en-GB', { 
                            timeZone: 'Europe/London',
                            hour12: false,
                            hour: '2-digit',
                            minute: '2-digit'
                          })}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm">{formatPnL(position.unrealized_pnl_usd || position.realized_pnl_usd)}</div>
                        <Badge variant={position.status === 'open' ? 'default' : 'secondary'} className="text-xs">
                          {position.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Dashboard;