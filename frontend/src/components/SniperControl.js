import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { Separator } from './ui/separator';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Settings, Zap, Shield, Target, AlertTriangle, Play, Square } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SniperControl = ({ botStatus }) => {
  const [config, setConfig] = useState({
    trade_amount_usd: 50,
    max_trade_amount_usd: 100,
    min_liquidity_usd: 10000,
    max_tax_buy_percent: 6,
    max_tax_sell_percent: 6,
    take_profit_targets: [10, 20, 30],
    take_profit_percentages: [50, 30, 20],
    stop_loss_percent: 50,
    max_position_time_minutes: 90,
    slippage_tolerance_percent: 12,
    is_active: true
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API}/config/trading`);
      setConfig(response.data);
    } catch (error) {
      console.error('Failed to fetch config:', error);
      toast.error('Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/config/trading`, config);
      toast.success('Configuration saved successfully!');
    } catch (error) {
      console.error('Failed to save config:', error);
      toast.error('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const updateConfig = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
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
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="glass animate-pulse">
            <CardHeader>
              <div className="h-6 bg-gray-600 rounded w-3/4"></div>
            </CardHeader>
            <CardContent className="space-y-4">
              {[...Array(4)].map((_, j) => (
                <div key={j} className="h-4 bg-gray-600 rounded"></div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header Controls */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl text-white flex items-center gap-2">
                <Settings className="h-5 w-5 text-blue-400" />
                Sniper Configuration
              </CardTitle>
              <CardDescription className="text-gray-400">
                Configure trading parameters and risk management settings
              </CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${
                  botStatus.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-500'
                }`}></div>
                <span className="text-sm text-gray-300">
                  {botStatus.is_running ? 'RUNNING' : 'STOPPED'}
                </span>
              </div>
              
              {botStatus.is_running ? (
                <Button 
                  onClick={stopSniper}
                  variant="destructive"
                  className="btn-danger"
                  data-testid="stop-sniper-btn"
                >
                  <Square className="h-4 w-4 mr-2" />
                  Stop Sniper
                </Button>
              ) : (
                <Button 
                  onClick={startSniper}
                  className="btn-success"
                  data-testid="start-sniper-btn"
                >
                  <Play className="h-4 w-4 mr-2" />
                  Start Sniper
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Configuration Tabs */}
      <Tabs defaultValue="trading" className="space-y-6">
        <TabsList className="bg-gray-800/50 border border-gray-700">
          <TabsTrigger value="trading" className="data-[state=active]:bg-blue-600">Trading</TabsTrigger>
          <TabsTrigger value="risk" className="data-[state=active]:bg-blue-600">Risk Management</TabsTrigger>
          <TabsTrigger value="advanced" className="data-[state=active]:bg-blue-600">Advanced</TabsTrigger>
        </TabsList>

        <TabsContent value="trading">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Trading Amounts */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Zap className="h-5 w-5 text-green-400" />
                  Trading Amounts
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Configure trade sizing and investment amounts
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Trade Amount
                    <Badge variant="outline">{formatCurrency(config.trade_amount_usd)}</Badge>
                  </Label>
                  <Slider
                    value={[config.trade_amount_usd]}
                    onValueChange={([value]) => updateConfig('trade_amount_usd', value)}
                    min={10}
                    max={1000}
                    step={5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>$10</span>
                    <span>$1,000</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Max Trade Amount
                    <Badge variant="outline">{formatCurrency(config.max_trade_amount_usd)}</Badge>
                  </Label>
                  <Slider
                    value={[config.max_trade_amount_usd]}
                    onValueChange={([value]) => updateConfig('max_trade_amount_usd', value)}
                    min={config.trade_amount_usd}
                    max={5000}
                    step={10}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>${config.trade_amount_usd}</span>
                    <span>$5,000</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Slippage Tolerance
                    <Badge variant="outline">{config.slippage_tolerance_percent}%</Badge>
                  </Label>
                  <Slider
                    value={[config.slippage_tolerance_percent]}
                    onValueChange={([value]) => updateConfig('slippage_tolerance_percent', value)}
                    min={1}
                    max={30}
                    step={0.5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>1%</span>
                    <span>30%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Take Profit Settings */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Target className="h-5 w-5 text-blue-400" />
                  Take Profit Targets
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Configure automatic profit-taking levels
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {config.take_profit_targets.map((target, index) => (
                  <div key={index} className="space-y-3 p-4 bg-gray-800/30 rounded-lg border border-gray-700">
                    <div className="flex items-center justify-between">
                      <Label className="text-gray-300">Target {index + 1}</Label>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">{target}x</Badge>
                        <Badge variant="outline">{config.take_profit_percentages[index]}%</Badge>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label className="text-xs text-gray-400">Multiplier (e.g., 10x = 1000% gain)</Label>
                      <Slider
                        value={[target]}
                        onValueChange={([value]) => {
                          const newTargets = [...config.take_profit_targets];
                          newTargets[index] = value;
                          updateConfig('take_profit_targets', newTargets);
                        }}
                        min={2}
                        max={100}
                        step={1}
                        className="w-full"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label className="text-xs text-gray-400">Sell Percentage</Label>
                      <Slider
                        value={[config.take_profit_percentages[index]]}
                        onValueChange={([value]) => {
                          const newPercentages = [...config.take_profit_percentages];
                          newPercentages[index] = value;
                          updateConfig('take_profit_percentages', newPercentages);
                        }}
                        min={5}
                        max={100}
                        step={5}
                        className="w-full"
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="risk">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Filters */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Shield className="h-5 w-5 text-red-400" />
                  Risk Filters
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Safety parameters to avoid risky tokens
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Minimum Liquidity
                    <Badge variant="outline">{formatCurrency(config.min_liquidity_usd)}</Badge>
                  </Label>
                  <Slider
                    value={[config.min_liquidity_usd]}
                    onValueChange={([value]) => updateConfig('min_liquidity_usd', value)}
                    min={1000}
                    max={100000}
                    step={1000}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>$1K</span>
                    <span>$100K</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Max Buy Tax
                    <Badge variant="outline">{config.max_tax_buy_percent}%</Badge>
                  </Label>
                  <Slider
                    value={[config.max_tax_buy_percent]}
                    onValueChange={([value]) => updateConfig('max_tax_buy_percent', value)}
                    min={0}
                    max={25}
                    step={0.5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>0%</span>
                    <span>25%</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Max Sell Tax
                    <Badge variant="outline">{config.max_tax_sell_percent}%</Badge>
                  </Label>
                  <Slider
                    value={[config.max_tax_sell_percent]}
                    onValueChange={([value]) => updateConfig('max_tax_sell_percent', value)}
                    min={0}
                    max={25}
                    step={0.5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>0%</span>
                    <span>25%</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Stop Loss & Timing */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-400" />
                  Stop Loss & Timing
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Position management and exit strategies
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Stop Loss
                    <Badge variant="outline">{config.stop_loss_percent}%</Badge>
                  </Label>
                  <Slider
                    value={[config.stop_loss_percent]}
                    onValueChange={([value]) => updateConfig('stop_loss_percent', value)}
                    min={10}
                    max={90}
                    step={5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>10% Loss</span>
                    <span>90% Loss</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-gray-300 flex items-center justify-between">
                    Max Position Time
                    <Badge variant="outline">{config.max_position_time_minutes}m</Badge>
                  </Label>
                  <Slider
                    value={[config.max_position_time_minutes]}
                    onValueChange={([value]) => updateConfig('max_position_time_minutes', value)}
                    min={5}
                    max={300}
                    step={5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-400">
                    <span>5min</span>
                    <span>5hr</span>
                  </div>
                </div>

                <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                  <div className="flex items-center gap-2 text-yellow-400 mb-2">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="font-medium text-sm">Risk Warning</span>
                  </div>
                  <p className="text-xs text-yellow-200/80">
                    High-frequency trading involves significant risk. Only trade with money you can afford to lose.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="advanced">
          <Card className="glass border-gray-700">
            <CardHeader>
              <CardTitle className="text-white">Advanced Settings</CardTitle>
              <CardDescription className="text-gray-400">
                Expert configuration options for experienced users
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="gas-price" className="text-gray-300">Gas Price (Gwei)</Label>
                    <Input
                      id="gas-price"
                      type="number"
                      placeholder="5"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="max-slippage" className="text-gray-300">Fast Mode Slippage (%)</Label>
                    <Input
                      id="max-slippage"
                      type="number"
                      placeholder="15"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="probe-percent" className="text-gray-300">Probe Buy (%)</Label>
                    <Input
                      id="probe-percent"
                      type="number"
                      placeholder="30"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="buy-delay" className="text-gray-300">Buy Delay (ms)</Label>
                    <Input
                      id="buy-delay"
                      type="number"
                      placeholder="250"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                </div>
              </div>
              
              <Separator className="bg-gray-700" />
              
              <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                <h4 className="font-medium text-blue-400 mb-2">Performance Optimization</h4>
                <p className="text-sm text-blue-200/80">
                  These settings affect reaction time and success rate. Lower delays increase speed but may reduce reliability.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Save Configuration */}
      <div className="flex justify-end">
        <Button 
          onClick={saveConfig}
          disabled={saving}
          className="btn-primary"
          data-testid="save-config-btn"
        >
          {saving ? 'Saving...' : 'Save Configuration'}
        </Button>
      </div>
    </div>
  );
};

export default SniperControl;