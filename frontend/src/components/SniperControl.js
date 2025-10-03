import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Activity, Zap, TrendingUp, AlertTriangle, PlayCircle, StopCircle, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Risk level badge component
const RiskBadge = ({ level }) => {
  const colors = {
    low: 'bg-green-500/20 text-green-400 border-green-500/30',
    medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    high: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  
  return (
    <Badge className={`${colors[level] || colors.medium} border`}>
      {level.toUpperCase()}
    </Badge>
  );
};

const ParadoxControl = ({ botStatus }) => {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalPairs: 0,
    activeTrades: 0,
    totalPnL: 0,
    winRate: 0,
  });

  useEffect(() => {
    fetchConfig();
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/config/trading`);
      setConfig(response.data);
    } catch (error) {
      console.error('Failed to fetch config:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const [statsRes, positionsRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/positions`),
      ]);
      
      const openPositions = positionsRes.data.filter(p => p.status === 'open' || p.status === 'partial');
      
      setStats({
        totalPairs: statsRes.data.pairs_detected || 0,
        activeTrades: openPositions.length,
        totalPnL: statsRes.data.total_pnl_usd || 0,
        winRate: statsRes.data.win_rate_percent || 0,
      });
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const startParadox = async () => {
    try {
      await axios.post(`${API}/sniper/start`);
      toast.success('Paradox bot started successfully!');
    } catch (error) {
      toast.error('Failed to start bot');
    }
  };

  const stopParadox = async () => {
    try {
      await axios.post(`${API}/sniper/stop`);
      toast.success('Paradox bot stopped');
    } catch (error) {
      toast.error('Failed to stop bot');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status Overview Card */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl text-white flex items-center gap-2">
                <Activity className="h-5 w-5 text-blue-400" />
                Paradox Configuration
              </CardTitle>
              <CardDescription className="text-gray-400">
                Real-time bot status and performance metrics
              </CardDescription>
            </div>
            
            <Badge className={`text-sm px-3 py-1 ${
              botStatus.is_running 
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
            }`}>
              {botStatus.is_running ? 'ACTIVE' : 'STOPPED'}
            </Badge>
          </div>
        </CardHeader>
        
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-gray-800/30 p-4 rounded-lg">
              <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
                <Zap className="h-4 w-4" />
                <span>Control</span>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={stopParadox}
                  disabled={!botStatus.is_running}
                  variant="destructive"
                  size="sm"
                  className="flex-1"
                  data-testid="stop-paradox-btn"
                >
                  <StopCircle className="h-4 w-4 mr-1" />
                  Stop
                </Button>
                <Button
                  onClick={startParadox}
                  disabled={botStatus.is_running}
                  size="sm"
                  className="flex-1 bg-green-600 hover:bg-green-700"
                  data-testid="start-paradox-btn"
                >
                  <PlayCircle className="h-4 w-4 mr-1" />
                  Start
                </Button>
              </div>
            </div>

            <div className="bg-gray-800/30 p-4 rounded-lg">
              <div className="text-gray-400 text-sm mb-1">Pairs Detected</div>
              <div className="text-white text-2xl font-bold">{stats.totalPairs}</div>
            </div>

            <div className="bg-gray-800/30 p-4 rounded-lg">
              <div className="text-gray-400 text-sm mb-1">Active Trades</div>
              <div className="text-white text-2xl font-bold">{stats.activeTrades}</div>
            </div>

            <div className="bg-gray-800/30 p-4 rounded-lg">
              <div className="text-gray-400 text-sm mb-1">Total P&L</div>
              <div className={`text-2xl font-bold ${stats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                ${stats.totalPnL.toFixed(2)}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configuration Summary */}
      {config && (
        <Card className="glass border-gray-700">
          <CardHeader>
            <CardTitle className="text-white">Current Configuration</CardTitle>
            <CardDescription className="text-gray-400">
              Active trading parameters and risk settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="space-y-2">
                <div className="text-sm text-gray-400">Trade Amount</div>
                <div className="text-white font-semibold">${config.trade_amount_usd}</div>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-gray-400">Min Liquidity</div>
                <div className="text-white font-semibold">${config.min_liquidity_usd?.toLocaleString()}</div>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-gray-400">Max Tax (Buy/Sell)</div>
                <div className="text-white font-semibold">{config.max_tax_buy_percent}% / {config.max_tax_sell_percent}%</div>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-gray-400">Take Profit Targets</div>
                <div className="text-white font-semibold">
                  {config.take_profit_targets?.join('x, ')}x
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-gray-400">Stop Loss</div>
                <div className="text-white font-semibold">{config.stop_loss_percent}%</div>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-gray-400">Slippage Tolerance</div>
                <div className="text-white font-semibold">{config.slippage_tolerance_percent}%</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-green-400" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchStats}
              className="border-blue-500 text-blue-400 hover:bg-blue-500/10"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh Stats
            </Button>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/config')}
              className="border-purple-500 text-purple-400 hover:bg-purple-500/10"
            >
              <AlertTriangle className="h-4 w-4 mr-2" />
              Modify Config
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ParadoxControl;