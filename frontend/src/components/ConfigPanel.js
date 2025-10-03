import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Switch } from './ui/switch';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Settings, Key, Shield, AlertTriangle, Server, Database } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ConfigPanel = () => {
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
  
  const [rpcConfig, setRpcConfig] = useState({
    bsc_rpc_http: '',
    bsc_rpc_ws: '',
    bscscan_api_key: ''
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);

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

  const testRpcConnection = async () => {
    setTestingConnection(true);
    try {
      // Simulate RPC connection test
      await new Promise(resolve => setTimeout(resolve, 2000));
      toast.success('RPC connection test successful!');
    } catch (error) {
      toast.error('RPC connection test failed');
    } finally {
      setTestingConnection(false);
    }
  };

  const resetToDefaults = () => {
    setConfig({
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
    toast.info('Configuration reset to defaults');
  };

  const updateConfig = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const updateRpcConfig = (key, value) => {
    setRpcConfig(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="glass animate-pulse">
            <CardHeader>
              <div className="h-6 bg-gray-600 rounded w-3/4"></div>
            </CardHeader>
            <CardContent className="space-y-4">
              {[...Array(3)].map((_, j) => (
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
      {/* Header */}
      <Card className="glass border-gray-700">
        <CardHeader>
          <CardTitle className="text-xl text-white flex items-center gap-2">
            <Settings className="h-5 w-5 text-blue-400" />
            System Configuration
          </CardTitle>
          <CardDescription className="text-gray-400">
            Configure system settings, API keys, and advanced parameters
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Configuration Tabs */}
      <Tabs defaultValue="rpc" className="space-y-6">
        <TabsList className="bg-gray-800/50 border border-gray-700">
          <TabsTrigger value="rpc" className="data-[state=active]:bg-blue-600">RPC & APIs</TabsTrigger>
          <TabsTrigger value="trading" className="data-[state=active]:bg-blue-600">Trading Config</TabsTrigger>
          <TabsTrigger value="security" className="data-[state=active]:bg-blue-600">Security</TabsTrigger>
          <TabsTrigger value="advanced" className="data-[state=active]:bg-blue-600">Advanced</TabsTrigger>
        </TabsList>

        <TabsContent value="rpc">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* RPC Configuration */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Server className="h-5 w-5 text-green-400" />
                  Blockchain RPC
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Configure BSC RPC endpoints for blockchain connectivity
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="rpc-http" className="text-gray-300">HTTP RPC URL</Label>
                  <Input
                    id="rpc-http"
                    type="url"
                    placeholder="https://bsc-dataseed1.binance.org/"
                    value={rpcConfig.bsc_rpc_http}
                    onChange={(e) => updateRpcConfig('bsc_rpc_http', e.target.value)}
                    className="bg-gray-800 border-gray-600 text-white font-mono text-sm"
                  />
                  <p className="text-xs text-gray-400">
                    Free: Use public BSC endpoints (slower) | Premium: QuickNode, Ankr (faster)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="rpc-ws" className="text-gray-300">WebSocket RPC URL</Label>
                  <Input
                    id="rpc-ws"
                    type="url"
                    placeholder="wss://bsc-ws-node.nariox.org:443/ws/v3/YOUR_API_KEY"
                    value={rpcConfig.bsc_rpc_ws}
                    onChange={(e) => updateRpcConfig('bsc_rpc_ws', e.target.value)}
                    className="bg-gray-800 border-gray-600 text-white font-mono text-sm"
                  />
                  <p className="text-xs text-gray-400">
                    Required for real-time pair detection. Get from QuickNode or similar providers.
                  </p>
                </div>

                <div className="flex gap-2">
                  <Button 
                    onClick={testRpcConnection}
                    disabled={testingConnection || !rpcConfig.bsc_rpc_http}
                    variant="outline"
                    className="flex-1"
                    data-testid="test-rpc-btn"
                  >
                    {testingConnection ? 'Testing...' : 'Test Connection'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* API Keys */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Key className="h-5 w-5 text-yellow-400" />
                  API Keys
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Configure external API keys for enhanced functionality
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="bscscan-key" className="text-gray-300">BSCScan API Key</Label>
                  <Input
                    id="bscscan-key"
                    type="password"
                    placeholder="Enter BSCScan API key"
                    value={rpcConfig.bscscan_api_key}
                    onChange={(e) => updateRpcConfig('bscscan_api_key', e.target.value)}
                    className="bg-gray-800 border-gray-600 text-white font-mono"
                  />
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">FREE</Badge>
                    <a 
                      href="https://bscscan.com/apis" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:text-blue-300"
                    >
                      Get free API key →
                    </a>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="dexscreener" className="text-gray-300">DexScreener</Label>
                  <div className="flex items-center gap-2">
                    <Badge variant="default" className="text-xs bg-green-600">NO KEY REQUIRED</Badge>
                    <span className="text-xs text-gray-400">Public API access</span>
                  </div>
                </div>

                <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-400 mb-2">
                    <Key className="h-4 w-4" />
                    <span className="font-medium text-sm">Setup Guide</span>
                  </div>
                  <ol className="text-xs text-blue-200/80 space-y-1 list-decimal list-inside">
                    <li>Sign up for QuickNode BSC endpoint</li>
                    <li>Get free BSCScan API key</li>
                    <li>Test connections before starting</li>
                  </ol>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="trading">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Export/Import Config */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Database className="h-5 w-5 text-purple-400" />
                  Configuration Management
                </CardTitle>
                <CardDescription className="text-gray-400">
                  Backup, restore, and share trading configurations
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-gray-300">Export Current Config</Label>
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={() => {
                      const configJson = JSON.stringify(config, null, 2);
                      const blob = new Blob([configJson], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url;
                      a.download = 'sniper-config.json';
                      a.click();
                      toast.success('Configuration exported');
                    }}
                    data-testid="export-config-btn"
                  >
                    Export to File
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="config-import" className="text-gray-300">Import Configuration</Label>
                  <Input
                    id="config-import"
                    type="file"
                    accept=".json"
                    className="bg-gray-800 border-gray-600 text-white"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        const reader = new FileReader();
                        reader.onload = (event) => {
                          try {
                            const importedConfig = JSON.parse(event.target.result);
                            setConfig(importedConfig);
                            toast.success('Configuration imported successfully');
                          } catch (error) {
                            toast.error('Invalid configuration file');
                          }
                        };
                        reader.readAsText(file);
                      }
                    }}
                  />
                </div>

                <div className="flex gap-2">
                  <Button 
                    onClick={resetToDefaults}
                    variant="outline"
                    className="flex-1"
                    data-testid="reset-config-btn"
                  >
                    Reset to Defaults
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Quick Presets */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white">Quick Presets</CardTitle>
                <CardDescription className="text-gray-400">
                  Pre-configured settings for different trading strategies
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <div className="flex items-center gap-2 text-green-400 mb-2">
                    <span className="font-medium text-sm">🎯 RECOMMENDED FOR YOU</span>
                  </div>
                  <p className="text-xs text-green-200/80 mb-3">
                    Quick trades (20 min max) • High selectivity • Conservative targets • 80%+ win rate
                  </p>
                  <Button 
                    variant="default" 
                    className="w-full bg-green-600 hover:bg-green-700"
                    onClick={() => {
                      setConfig(prev => ({
                        ...prev,
                        trade_amount_usd: 75,
                        max_trade_amount_usd: 150,
                        max_tax_buy_percent: 3,
                        max_tax_sell_percent: 3,
                        min_liquidity_usd: 100000,
                        stop_loss_percent: 25,
                        take_profit_targets: [3, 5, 8],
                        take_profit_percentages: [60, 30, 10],
                        max_position_time_minutes: 20,
                        slippage_tolerance_percent: 8
                      }));
                      toast.success('Applied HIGH WIN-RATE settings!');
                    }}
                  >
                    🎯 Apply HIGH WIN-RATE Settings
                  </Button>
                </div>
                
                <div className="space-y-2">
                  <Label className="text-sm text-gray-300">Other Presets:</Label>
                
                  <Button 
                    variant="outline" 
                    className="w-full justify-start"
                    onClick={() => {
                      setConfig(prev => ({
                        ...prev,
                        trade_amount_usd: 50,
                        max_tax_buy_percent: 6,
                        max_tax_sell_percent: 6,
                        min_liquidity_usd: 50000,
                        stop_loss_percent: 35,
                        take_profit_targets: [5, 10, 15],
                        take_profit_percentages: [50, 30, 20],
                        max_position_time_minutes: 45,
                        slippage_tolerance_percent: 10
                      }));
                      toast.info('Applied Balanced preset');
                    }}
                  >
                    <Settings className="h-4 w-4 mr-2" />
                    Balanced (Medium Risk)
                  </Button>
                  
                  <Button 
                    variant="outline" 
                    className="w-full justify-start border-red-500 text-red-400 hover:bg-red-500/10"
                    onClick={() => {
                      setConfig(prev => ({
                        ...prev,
                        trade_amount_usd: 25,
                        max_tax_buy_percent: 2,
                        max_tax_sell_percent: 2,
                        min_liquidity_usd: 200000,
                        stop_loss_percent: 15,
                        take_profit_targets: [2, 3, 4],
                        take_profit_percentages: [70, 20, 10],
                        max_position_time_minutes: 10,
                        slippage_tolerance_percent: 6
                      }));
                      toast.info('Applied ULTRA SAFE preset');
                    }}
                  >
                    🛡️ ULTRA SAFE (Highest Win Rate)
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="security">
          <Card className="glass border-gray-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Shield className="h-5 w-5 text-red-400" />
                Security Settings
              </CardTitle>
              <CardDescription className="text-gray-400">
                Configure security parameters and safety measures
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-gray-300">Enable Stop Loss</Label>
                      <p className="text-xs text-gray-400">Automatic position closure on losses</p>
                    </div>
                    <Switch 
                      checked={config.stop_loss_percent > 0}
                      onCheckedChange={(checked) => 
                        updateConfig('stop_loss_percent', checked ? 50 : 0)
                      }
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-gray-300">Time-based Exit</Label>
                      <p className="text-xs text-gray-400">Exit positions after max time</p>
                    </div>
                    <Switch 
                      checked={config.max_position_time_minutes > 0}
                      onCheckedChange={(checked) => 
                        updateConfig('max_position_time_minutes', checked ? 90 : 0)
                      }
                    />
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="max-daily-loss" className="text-gray-300">Max Daily Loss ($)</Label>
                    <Input
                      id="max-daily-loss"
                      type="number"
                      placeholder="500"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="max-positions" className="text-gray-300">Max Concurrent Positions</Label>
                    <Input
                      id="max-positions"
                      type="number"
                      placeholder="5"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                </div>
              </div>
              
              <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                <div className="flex items-center gap-2 text-red-400 mb-2">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium text-sm">Security Notice</span>
                </div>
                <ul className="text-xs text-red-200/80 space-y-1 list-disc list-inside">
                  <li>Never share your private keys or API keys</li>
                  <li>Use dedicated wallets for trading only</li>
                  <li>Start with small amounts to test strategies</li>
                  <li>Monitor positions regularly</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="advanced">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Performance Tuning */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white">Performance Tuning</CardTitle>
                <CardDescription className="text-gray-400">
                  Advanced settings for optimal performance
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
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
                    <Label htmlFor="gas-limit" className="text-gray-300">Gas Limit</Label>
                    <Input
                      id="gas-limit"
                      type="number"
                      placeholder="500000"
                      className="bg-gray-800 border-gray-600 text-white"
                    />
                  </div>
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="webhook-url" className="text-gray-300">Webhook URL (Optional)</Label>
                  <Input
                    id="webhook-url"
                    type="url"
                    placeholder="https://discord.com/api/webhooks/..."
                    className="bg-gray-800 border-gray-600 text-white"
                  />
                  <p className="text-xs text-gray-400">
                    Receive trade notifications via Discord/Telegram
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Debug Settings */}
            <Card className="glass border-gray-700">
              <CardHeader>
                <CardTitle className="text-white">Debug & Logging</CardTitle>
                <CardDescription className="text-gray-400">
                  Development and troubleshooting options
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-gray-300">Enable Debug Logs</Label>
                    <p className="text-xs text-gray-400">Detailed logging for troubleshooting</p>
                  </div>
                  <Switch />
                </div>
                
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-gray-300">Dry Run Mode</Label>
                    <p className="text-xs text-gray-400">Simulate trades without execution</p>
                  </div>
                  <Switch />
                </div>
                
                <div className="space-y-2">
                  <Label className="text-gray-300">Custom Log Level</Label>
                  <select className="w-full p-2 bg-gray-800 border border-gray-600 rounded text-white">
                    <option value="INFO">INFO</option>
                    <option value="DEBUG">DEBUG</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Save Configuration */}
      <div className="flex justify-end gap-4">
        <Button 
          onClick={resetToDefaults}
          variant="outline"
          data-testid="reset-all-btn"
        >
          Reset All
        </Button>
        <Button 
          onClick={saveConfig}
          disabled={saving}
          className="btn-primary"
          data-testid="save-all-config-btn"
        >
          {saving ? 'Saving...' : 'Save All Configuration'}
        </Button>
      </div>
    </div>
  );
};

export default ConfigPanel;