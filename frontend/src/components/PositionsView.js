import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Progress } from './ui/progress';
import { Wallet, TrendingUp, TrendingDown, Clock, Target, X, ExternalLink } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PositionsView = ({ ws, selectedWalletId }) => {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [closingPosition, setClosingPosition] = useState(null);
  const [tradingConfig, setTradingConfig] = useState(null);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, [selectedWalletId]); // Refresh when wallet changes

  // Listen for WebSocket updates
  useEffect(() => {
    if (ws) {
      const handleMessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'position_closed' || message.type === 'positions_bulk_closed' || message.type === 'demo_position_created') {
          // Refresh positions immediately when they change
          fetchPositions();
          if (message.type === 'position_closed') {
            toast.success(`Position closed: ${message.data.token_symbol} - P&L: $${message.data.realized_pnl?.toFixed(2) || 'N/A'}`);
          }
        }
      };
      
      ws.addEventListener('message', handleMessage);
      return () => ws.removeEventListener('message', handleMessage);
    }
  }, [ws]);

  const fetchPositions = async () => {
    try {
      const positionsUrl = selectedWalletId 
        ? `${API}/positions?wallet_id=${selectedWalletId}` 
        : `${API}/positions`;
      const positionsRes = await axios.get(positionsUrl);
      
      const walletsRes = await axios.get(`${API}/wallets`);
      
      // Fetch current trading config for TP targets
      const configRes = await axios.get(`${API}/config/trading`);
      setTradingConfig(configRes.data);
      
      // Add wallet names to positions
      const positionsWithWallets = positionsRes.data.map(position => {
        const wallet = walletsRes.data.find(w => w.id === position.wallet_id);
        return {
          ...position,
          wallet_name: wallet ? wallet.name : 'Unknown Wallet'
        };
      });
      
      setPositions(positionsWithWallets);
    } catch (error) {
      console.error('Failed to fetch positions:', error);
      toast.error('Failed to load positions');
    } finally {
      setLoading(false);
    }
  };

  const closePosition = async (positionId) => {
    setClosingPosition(positionId);
    try {
      await axios.post(`${API}/positions/${positionId}/close`);
      toast.success('Position close requested');
      await fetchPositions(); // Refresh positions
    } catch (error) {
      console.error('Failed to close position:', error);
      toast.error('Failed to close position');
    } finally {
      setClosingPosition(null);
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

  const getStatusBadge = (status) => {
    const statusConfig = {
      open: { variant: 'default', color: 'bg-green-500' },
      partial: { variant: 'secondary', color: 'bg-yellow-500' },
      closed: { variant: 'outline', color: 'bg-gray-500' },
      failed: { variant: 'destructive', color: 'bg-red-500' }
    };
    return statusConfig[status] || statusConfig.open;
  };

  const calculateTimeHeld = (entryTime, exitTime = null) => {
    try {
      // Parse times in UTC to avoid timezone issues
      const end = exitTime ? new Date(exitTime + 'Z') : new Date();
      const start = new Date(entryTime + 'Z'); // Ensure UTC parsing
      
      // Calculate difference in milliseconds
      const diffMs = end.getTime() - start.getTime();
      
      // Ensure we don't show negative time
      if (diffMs < 0) return "0m";
      
      const totalMinutes = Math.floor(diffMs / 60000);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;
      const days = Math.floor(hours / 24);
      
      if (days > 0) return `${days}d ${hours % 24}h`;
      if (hours > 0) return `${hours}h ${minutes}m`;
      return `${totalMinutes}m`;
    } catch (error) {
      console.error('Error calculating time held:', error);
      return "0m";
    }
  };

  const getTakeProfitProgress = (position) => {
    if (!position.take_profits_hit || position.take_profits_hit.length === 0) {
      const total = tradingConfig?.take_profit_targets?.length || 3;
      return { progress: 0, completed: 0, total };
    }
    const completed = position.take_profits_hit.length;
    const total = tradingConfig?.take_profit_targets?.length || 3;
    const progress = (completed / total) * 100;
    return { progress, completed, total };
  };

  const openInBSCScan = (address) => {
    window.open(`https://bscscan.com/address/${address}`, '_blank');
  };

  const activePositions = positions.filter(p => p.status === 'open');
  const closedPositions = positions.filter(p => p.status !== 'open');

  if (loading) {
    return (
      <div className="space-y-6">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="glass animate-pulse">
            <CardContent className="p-6">
              <div className="space-y-4">
                <div className="h-6 bg-gray-600 rounded w-1/3"></div>
                <div className="grid grid-cols-4 gap-4">
                  {[...Array(4)].map((_, j) => (
                    <div key={j} className="h-4 bg-gray-600 rounded"></div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <CardTitle className="text-xl text-white flex items-center gap-2">
            <Wallet className="h-5 w-5 text-blue-400" />
            Positions Management
          </CardTitle>
          <CardDescription className="text-gray-400">
            Monitor and manage your trading positions across all active trades
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Position Tabs */}
      <Tabs defaultValue="active" className="space-y-6">
        <TabsList className="bg-gray-800/50 border border-gray-700">
          <TabsTrigger value="active" className="data-[state=active]:bg-blue-600">
            Active Positions ({activePositions.length})
          </TabsTrigger>
          <TabsTrigger value="history" className="data-[state=active]:bg-blue-600">
            Position History ({closedPositions.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active">
          <div className="space-y-4">
            {activePositions.length === 0 ? (
              <Card className="glass border-gray-700">
                <CardContent className="p-12 text-center">
                  <Wallet className="h-12 w-12 mx-auto mb-4 text-gray-500" />
                  <h3 className="text-lg font-medium text-gray-300 mb-2">No Active Positions</h3>
                  <p className="text-gray-400">
                    Your active trading positions will appear here when the sniper executes trades.
                  </p>
                </CardContent>
              </Card>
            ) : (
              activePositions.map((position) => {
                const tpProgress = getTakeProfitProgress(position);
                return (
                  <Card key={position.id} className="glass border-gray-700 hover:border-gray-600 transition-colors" data-testid="position-card">
                    <CardContent className="p-6">
                      {/* Header Row */}
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-4">
                          <div>
                            <h3 className="text-xl font-bold text-white">{position.token_symbol}</h3>
                            <div className="flex items-center gap-2 mt-1">
                              <span className="text-xs text-gray-400 font-mono">
                                {position.token_address?.slice(0, 8)}...{position.token_address?.slice(-6)}
                              </span>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openInBSCScan(position.token_address)}
                                className="h-6 w-6 p-0 text-gray-400 hover:text-white"
                              >
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                          <Badge {...getStatusBadge(position.status)}>
                            {position.status.toUpperCase()}
                          </Badge>
                        </div>
                        
                        <div className="text-right">
                          <div className="text-2xl font-bold">
                            {formatPnL(position.unrealized_pnl_usd)}
                          </div>
                          <div className="text-lg">
                            {formatPnL(position.unrealized_pnl_percent, true)}
                          </div>
                        </div>
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                        <div className="bg-gray-800/30 p-3 rounded-lg">
                          <div className="text-xs text-gray-400 mb-1">Entry Value</div>
                          <div className="text-white font-semibold">{formatCurrency(position.entry_amount_usd)}</div>
                          <div className="text-xs text-gray-400">{position.entry_amount_bnb?.toFixed(4)} BNB</div>
                        </div>
                        
                        <div className="bg-gray-800/30 p-3 rounded-lg">
                          <div className="text-xs text-gray-400 mb-1">Current Value</div>
                          <div className="text-white font-semibold">{formatCurrency(position.current_value_usd)}</div>
                          <div className="text-xs text-gray-400">{position.tokens_held?.toLocaleString()} tokens</div>
                        </div>
                        
                        <div className="bg-gray-800/30 p-3 rounded-lg">
                          <div className="text-xs text-gray-400 mb-1">Time Held</div>
                          <div className="text-white font-semibold flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {calculateTimeHeld(position.entry_time)}
                          </div>
                        </div>
                        
                        <div className="bg-gray-800/30 p-3 rounded-lg">
                          <div className="text-xs text-gray-400 mb-1">Take Profits</div>
                          <div className="text-white font-semibold flex items-center gap-2">
                            <Target className="h-3 w-3" />
                            {tpProgress.completed}/{tpProgress.total}
                          </div>
                          <Progress value={tpProgress.progress} className="h-1 mt-1" />
                        </div>
                      </div>

                      {/* Take Profit Levels */}
                      <div className="mb-4">
                        <div className="text-sm text-gray-400 mb-2">Take Profit Levels</div>
                        <div className="grid grid-cols-3 gap-2">
                          {(tradingConfig?.take_profit_targets || [10, 20, 30]).map((target, index) => {
                            const isHit = position.take_profits_hit?.includes(target);
                            return (
                              <div key={target} className={`p-2 rounded border ${
                                isHit 
                                  ? 'bg-green-500/20 border-green-500/50 text-green-400'
                                  : 'bg-gray-800/30 border-gray-600 text-gray-400'
                              }`}>
                                <div className="text-xs text-center">
                                  {target}x {isHit && '✓'}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center justify-between pt-4 border-t border-gray-700">
                        <div className="text-xs text-gray-400">
                          Entry: {new Date(new Date(position.entry_time).getTime() + (60 * 60 * 1000)).toLocaleString('en-GB')}
                        </div>
                        
                        <Button
                          onClick={() => closePosition(position.id)}
                          disabled={closingPosition === position.id}
                          variant="destructive"
                          size="sm"
                          className="btn-danger"
                          data-testid="close-position-btn"
                        >
                          {closingPosition === position.id ? (
                            'Closing...'
                          ) : (
                            <>
                              <X className="h-4 w-4 mr-1" />
                              Close Position
                            </>
                          )}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        </TabsContent>

        <TabsContent value="history">
          <div className="space-y-4">
            {closedPositions.length === 0 ? (
              <Card className="glass border-gray-700">
                <CardContent className="p-12 text-center">
                  <Clock className="h-12 w-12 mx-auto mb-4 text-gray-500" />
                  <h3 className="text-lg font-medium text-gray-300 mb-2">No Position History</h3>
                  <p className="text-gray-400">
                    Completed trades and position history will appear here.
                  </p>
                </CardContent>
              </Card>
            ) : (
              closedPositions.map((position) => (
                <Card key={position.id} className="glass border-gray-700" data-testid="history-position-card">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-white">{position.token_symbol}</h4>
                            <Badge {...getStatusBadge(position.status)}>
                              {position.status.toUpperCase()}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-4 text-xs text-gray-400 mt-1">
                            <span>Entry: {formatCurrency(position.entry_amount_usd)}</span>
                            <span>Hold: {calculateTimeHeld(position.entry_time, position.exit_time)}</span>
                            <span>{new Date(new Date(position.entry_time).getTime() + (60 * 60 * 1000)).toLocaleDateString('en-GB')}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="text-right">
                        <div className="text-lg font-bold">
                          {formatPnL(position.realized_pnl_usd || position.unrealized_pnl_usd)}
                        </div>
                        <div className="text-sm">
                          {formatPnL((position.realized_pnl_usd || position.unrealized_pnl_usd) / position.entry_amount_usd * 100, true)}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PositionsView;