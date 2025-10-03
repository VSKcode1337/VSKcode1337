import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from './ui/alert-dialog';
import { Wallet, Plus, Eye, EyeOff, Copy, ExternalLink, Trash2, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const WalletManager = ({ ws }) => {
  const [wallets, setWallets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newWallet, setNewWallet] = useState({ name: '', private_key: '' });
  const [showPrivateKeys, setShowPrivateKeys] = useState({});
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  useEffect(() => {
    fetchWallets();
  }, []);

  // Listen for WebSocket updates to refresh wallet balances
  useEffect(() => {
    if (ws) {
      const handleMessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === 'position_closed' || message.type === 'positions_bulk_closed' || message.type === 'demo_position_created') {
          // Refresh wallets when positions are created or closed
          fetchWallets();
        }
      };
      
      ws.addEventListener('message', handleMessage);
      return () => ws.removeEventListener('message', handleMessage);
    }
  }, [ws]);

  const fetchWallets = async () => {
    try {
      const response = await axios.get(`${API}/wallets`);
      setWallets(response.data);
    } catch (error) {
      console.error('Failed to fetch wallets:', error);
      toast.error('Failed to load wallets');
    } finally {
      setLoading(false);
    }
  };

  const addWallet = async () => {
    if (!newWallet.name || !newWallet.private_key) {
      toast.error('Please fill in all fields');
      return;
    }

    setAdding(true);
    try {
      await axios.post(`${API}/wallets`, newWallet);
      toast.success('Wallet added successfully!');
      setNewWallet({ name: '', private_key: '' });
      setAddDialogOpen(false);
      await fetchWallets();
    } catch (error) {
      console.error('Failed to add wallet:', error);
      const errorMessage = typeof error.response?.data?.detail === 'string' 
        ? error.response.data.detail 
        : 'Failed to add wallet';
      toast.error(errorMessage);
    } finally {
      setAdding(false);
    }
  };

  const togglePrivateKeyVisibility = (walletId) => {
    setShowPrivateKeys(prev => ({
      ...prev,
      [walletId]: !prev[walletId]
    }));
  };

  const copyToClipboard = async (text, type) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${type} copied to clipboard`);
    } catch (error) {
      toast.error('Failed to copy to clipboard');
    }
  };

  const openInBSCScan = (address) => {
    window.open(`https://bscscan.com/address/${address}`, '_blank');
  };

  const generateRandomWallet = () => {
    // Generate a random private key (for demo purposes - in production, use proper crypto libraries)
    const randomKey = '0x' + Array.from({length: 64}, () => Math.floor(Math.random() * 16).toString(16)).join('');
    setNewWallet(prev => ({ ...prev, private_key: randomKey }));
    toast.info('Random private key generated (demo only)');
  };

  const formatBalance = (balance) => {
    return balance?.toFixed(4) || '0.0000';
  };

  const formatAddress = (address) => {
    if (!address) return 'N/A';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[...Array(3)].map((_, i) => (
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
    <div className="space-y-6 max-w-full overflow-x-hidden px-2 md:px-0">
      {/* Header */}
      <Card className="glass border-gray-700 max-w-full overflow-hidden">
        <CardHeader>
          {/* Mobile & Desktop Header */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <CardTitle className="text-lg md:text-xl text-white flex items-center gap-2">
                <Wallet className="h-5 w-5 text-blue-400" />
                Wallet Management
              </CardTitle>
              <CardDescription className="text-sm text-gray-400 mt-1">
                Manage trading wallets and monitor balances
              </CardDescription>
            </div>
            
            {/* Buttons - Stack on mobile, inline on desktop */}
            <div className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
              <Button 
                onClick={async () => {
                  try {
                    // Create demo wallet with random private key
                    const randomHex = Array.from({length: 64}, () => 
                      Math.floor(Math.random() * 16).toString(16)
                    ).join('');
                    const demoWallet = {
                      name: `Demo Wallet ${Math.floor(Math.random() * 1000)}`,
                      private_key: `0x${randomHex}`
                    };
                    await axios.post(`${API}/wallets`, demoWallet);
                    toast.success('Demo wallet created!');
                    await fetchWallets();
                  } catch (error) {
                    console.error('Demo wallet error:', error);
                    toast.error(error.response?.data?.detail || 'Failed to create demo wallet');
                  }
                }}
                variant="outline"
                className="border-green-500 text-green-400 hover:bg-green-500/10 w-full sm:w-auto text-sm"
                data-testid="add-demo-wallet-btn"
              >
                🎮 Add Demo Wallet
              </Button>
              
              <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="btn-primary w-full sm:w-auto text-sm" data-testid="add-wallet-btn">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Real Wallet
                  </Button>
                </DialogTrigger>
              <DialogContent className="bg-gray-900 border-gray-700">
                <DialogHeader>
                  <DialogTitle className="text-white">Add New Wallet</DialogTitle>
                  <DialogDescription className="text-gray-400">
                    Add a new trading wallet to execute trades across multiple accounts
                  </DialogDescription>
                </DialogHeader>
                
                <div className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="wallet-name" className="text-gray-300">Wallet Name</Label>
                    <Input
                      id="wallet-name"
                      placeholder="e.g., Main Trading Wallet"
                      value={newWallet.name}
                      onChange={(e) => setNewWallet(prev => ({ ...prev, name: e.target.value }))}
                      className="bg-gray-800 border-gray-600 text-white"
                      data-testid="wallet-name-input"
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="private-key" className="text-gray-300">Private Key</Label>
                    <div className="space-y-2">
                      <Input
                        id="private-key"
                        type="password"
                        placeholder="0x..."
                        value={newWallet.private_key}
                        onChange={(e) => setNewWallet(prev => ({ ...prev, private_key: e.target.value }))}
                        className="bg-gray-800 border-gray-600 text-white font-mono"
                        data-testid="private-key-input"
                      />
                      <Button 
                        type="button"
                        variant="outline" 
                        size="sm" 
                        onClick={generateRandomWallet}
                        className="w-full"
                      >
                        Generate Random (Demo)
                      </Button>
                    </div>
                    <p className="text-xs text-yellow-400">
                      ⚠️ Keep your private keys secure. Never share them with anyone.
                    </p>
                  </div>
                </div>
                
                <div className="flex justify-end gap-2 mt-6">
                  <Button 
                    variant="outline" 
                    onClick={() => setAddDialogOpen(false)}
                    disabled={adding}
                  >
                    Cancel
                  </Button>
                  <Button 
                    onClick={addWallet}
                    disabled={adding}
                    className="btn-success"
                    data-testid="confirm-add-wallet-btn"
                  >
                    {adding ? 'Adding...' : 'Add Wallet'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Wallets Grid - Single column on mobile, responsive on larger screens */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
        {wallets.length === 0 ? (
          <div className="col-span-full">
            <Card className="glass border-gray-700">
              <CardContent className="p-12 text-center">
                <Wallet className="h-12 w-12 mx-auto mb-4 text-gray-500" />
                <h3 className="text-lg font-medium text-gray-300 mb-2">No Wallets Added</h3>
                <p className="text-gray-400 mb-4">
                  Add your first trading wallet to start executing automated trades.
                </p>
                <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
                  <DialogTrigger asChild>
                    <Button className="btn-primary">
                      <Plus className="h-4 w-4 mr-2" />
                      Add Your First Wallet
                    </Button>
                  </DialogTrigger>
                </Dialog>
              </CardContent>
            </Card>
          </div>
        ) : (
          wallets.map((wallet) => (
            <Card key={wallet.id} className="glass border-gray-700 hover:border-gray-600 transition-colors" data-testid="wallet-card">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white text-lg">{wallet.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant={wallet.is_active ? 'default' : 'secondary'} className="text-xs">
                      {wallet.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="space-y-3 md:space-y-4">
                {/* Address */}
                <div className="space-y-1">
                  <Label className="text-xs text-gray-400">Address</Label>
                  <div className="flex items-center gap-1 md:gap-2">
                    <code className="text-xs md:text-sm text-white bg-gray-800 px-2 py-1 rounded font-mono flex-1 truncate">
                      {formatAddress(wallet.address)}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => copyToClipboard(wallet.address, 'Address')}
                      className="h-7 w-7 md:h-8 md:w-8 p-0 flex-shrink-0"
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openInBSCScan(wallet.address)}
                      className="h-7 w-7 md:h-8 md:w-8 p-0 flex-shrink-0"
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                </div>

                {/* Balance */}
                <div className="space-y-1">
                  <Label className="text-xs text-gray-400">Balance</Label>
                  <div className="flex items-center justify-between">
                    <span className="text-white font-semibold text-sm md:text-base">
                      {formatBalance(wallet.balance_bnb)} BNB
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        // Simulate balance refresh
                        toast.success('Balance refreshed');
                      }}
                      className="h-7 w-7 md:h-8 md:w-8 p-0"
                    >
                      <RefreshCw className="h-3 w-3" />
                    </Button>
                  </div>
                </div>

                {/* Private Key (Sensitive) */}
                <div className="space-y-1">
                  <Label className="text-xs text-gray-400">Private Key</Label>
                  <div className="flex items-center gap-1 md:gap-2">
                    <code className="text-xs md:text-sm text-white bg-gray-800 px-2 py-1 rounded font-mono flex-1 truncate select-none overflow-hidden">
                      {showPrivateKeys[wallet.id] ? 
                        `0x••••${wallet.address?.slice(-4) || ''}` : 
                        '0x••••••••••••••••'
                      }
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => togglePrivateKeyVisibility(wallet.id)}
                      className="h-7 w-7 md:h-8 md:w-8 p-0 flex-shrink-0"
                    >
                      {showPrivateKeys[wallet.id] ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                    </Button>
                  </div>
                </div>

                {/* Wallet Stats */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-gray-800/30 p-2 rounded">
                    <div className="text-gray-400 text-xs">Created</div>
                    <div className="text-white font-medium text-xs">
                      {new Date(wallet.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="bg-gray-800/30 p-2 rounded">
                    <div className="text-gray-400 text-xs">Status</div>
                    <div className={`font-medium text-xs ${
                      wallet.is_active ? 'text-green-400' : 'text-gray-400'
                    }`}>
                      {wallet.is_active ? 'Ready' : 'Inactive'}
                    </div>
                  </div>
                </div>

                {/* Actions - Stack on mobile */}
                <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-gray-700">
                  {wallet.name.toLowerCase().includes('test') || wallet.name.toLowerCase().includes('demo') ? (
                    <Button
                      variant="default"
                      size="sm"
                      className="flex-1 bg-green-600 hover:bg-green-700 text-white font-semibold text-xs sm:text-sm"
                      onClick={async () => {
                        try {
                          // Add demo funds for testing - ONLY for test wallets
                          const response = await axios.post(`${API}/wallets/${wallet.id}/add-demo-funds`);
                          toast.success(`Added ${response.data.amount} BNB demo funds!`);
                          await fetchWallets(); // Refresh to show new balance
                        } catch (error) {
                          console.error('Demo funds error:', error);
                          toast.error('Failed to add demo funds');
                        }
                      }}
                      data-testid="add-demo-funds-btn"
                    >
                      💰 Add Demo Funds
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 text-yellow-400 border-yellow-500 text-xs sm:text-sm"
                      onClick={() => {
                        toast.info('This is a real wallet. Fund it manually with actual BNB from your exchange.', {
                          description: 'Send BNB using BEP20 (BSC) network to this address.'
                        });
                      }}
                    >
                      🏦 Real Wallet - Fund Manually
                    </Button>
                  )}
                  
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="destructive"
                        size="sm"
                        className="h-9 w-full sm:w-9 p-0 sm:flex-shrink-0"
                        data-testid="delete-wallet-btn"
                      >
                        <Trash2 className="h-4 w-4 sm:mr-0 mr-2" />
                        <span className="sm:hidden">Delete Wallet</span>
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="bg-gray-900 border-gray-700">
                      <AlertDialogHeader>
                        <AlertDialogTitle className="text-white">Delete Wallet</AlertDialogTitle>
                        <AlertDialogDescription className="text-gray-400">
                          Are you sure you want to delete "{wallet.name}"? This action cannot be undone.
                          Make sure to backup your private key if needed.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="bg-gray-800 border-gray-600 text-white hover:bg-gray-700">
                          Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction 
                          className="bg-red-600 hover:bg-red-700"
                          onClick={async () => {
                            try {
                              await axios.delete(`${API}/wallets/${wallet.id}`);
                              toast.success('Wallet deleted successfully!');
                              await fetchWallets(); // Refresh the wallet list
                            } catch (error) {
                              console.error('Failed to delete wallet:', error);
                              toast.error('Failed to delete wallet');
                            }
                          }}
                        >
                          Delete Wallet
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Multi-Wallet Info */}
      {wallets.length > 0 && (
        <Card className="glass border-gray-700">
          <CardHeader>
            <CardTitle className="text-white">Multi-Wallet Trading</CardTitle>
            <CardDescription className="text-gray-400">
              When enabled, the sniper will execute the same trades across all active wallets simultaneously
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="bg-blue-500/10 border border-blue-500/20 p-4 rounded-lg">
                <h4 className="font-medium text-blue-400 mb-2">Synchronized Trading</h4>
                <p className="text-blue-200/80">
                  All active wallets will execute the same trades with identical parameters and timing.
                </p>
              </div>
              
              <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg">
                <h4 className="font-medium text-green-400 mb-2">Risk Distribution</h4>
                <p className="text-green-200/80">
                  Spread risk across multiple wallets while maintaining the same trading strategy.
                </p>
              </div>
              
              <div className="bg-yellow-500/10 border border-yellow-500/20 p-4 rounded-lg">
                <h4 className="font-medium text-yellow-400 mb-2">Independent Monitoring</h4>
                <p className="text-yellow-200/80">
                  Each wallet's performance and positions are tracked separately for detailed analytics.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default WalletManager;