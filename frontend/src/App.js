import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { LayoutDashboard, Zap, Briefcase, Settings, Wallet } from 'lucide-react';
import '@/App.css';

// Components
import Dashboard from './components/Dashboard';
import SniperControl from './components/SniperControl';
import PositionsView from './components/PositionsView';
import ConfigPanel from './components/ConfigPanel';
import WalletManager from './components/WalletManager';
import { Toaster } from './components/ui/sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Navigation Button Component - Mobile Responsive
const NavButton = ({ href, label, mobileLabel, icon: Icon }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isActive = location.pathname === href;
  
  return (
    <button
      onClick={() => navigate(href)}
      className={`px-3 md:px-6 py-2 md:py-3 rounded-xl font-medium transition-all duration-200 text-sm md:text-base flex items-center gap-2 ${
        isActive 
          ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' 
          : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
      }`}
      data-testid={`nav-${href.replace('/', '') || 'dashboard'}`}
    >
      {Icon && <Icon className="h-4 w-4" />}
      <span className="hidden md:inline">{label}</span>
      <span className="md:hidden">{mobileLabel || label}</span>
    </button>
  );
};

// Main App Content Component
const AppContent = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true); // Add connecting state
  const [botStatus, setBotStatus] = useState({
    is_running: false,
    connected_clients: 0,
    active_positions: 0,
    detected_pairs_today: 0,
    blockchain_connected: false,
    last_block: null
  });
  const [ws, setWs] = useState(null);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Initialize WebSocket connection
  useEffect(() => {
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    let websocketRef = null;
    
    const connectWebSocket = () => {
      try {
        setIsConnecting(true); // Set connecting state
        const wsUrl = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';
        console.log('Connecting to WebSocket:', wsUrl);
        const websocket = new WebSocket(wsUrl);
        websocketRef = websocket;

        websocket.onopen = () => {
          console.log('✅ WebSocket connected successfully');
          setIsConnected(true);
          setIsConnecting(false); // Clear connecting state
          setWs(websocket);
          reconnectAttempts = 0; // Reset attempts on successful connection
        };

        websocket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        websocket.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          setIsConnected(false);
          setIsConnecting(false);
          setWs(null);
          
          // Try to reconnect if under max attempts
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            setIsConnecting(true); // Show connecting during reconnect
            console.log(`Reconnect attempt ${reconnectAttempts}/${maxReconnectAttempts} in 3 seconds...`);
            setTimeout(connectWebSocket, 3000);
          } else {
            console.error('Max WebSocket reconnection attempts reached');
          }
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          // Don't set isConnected to false here - wait for onclose
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        setIsConnected(false);
        setIsConnecting(false);
      }
    };

    connectWebSocket();
    
    // Cleanup on unmount
    return () => {
      if (websocketRef) {
        websocketRef.close();
      }
    };
  }, []);

  // Fetch bot status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`${API}/status`);
        console.log('Bot status updated:', response.data);
        setBotStatus(response.data);
      } catch (error) {
        console.error('Failed to fetch bot status:', error);
      }
    };

    // Fetch immediately on mount
    fetchStatus();
    
    // Then fetch every 10 seconds
    const interval = setInterval(fetchStatus, 10000);

    return () => clearInterval(interval);
  }, []);

  // Update current time every second
  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timeInterval);
  }, []);

  // Update current time every second
  useEffect(() => {
    const timeInterval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timeInterval);
  }, []);

  const handleWebSocketMessage = (message) => {
    switch (message.type) {
      case 'connection_established':
        console.log('WebSocket connection established');
        break;
      case 'status_update':
        setBotStatus(prev => ({ ...prev, is_running: message.data.status === 'started' }));
        break;
      case 'new_pair_detected':
        console.log('New pair detected:', message.data);
        // Update detected pairs count and force dashboard refresh
        setBotStatus(prev => ({ 
          ...prev, 
          detected_pairs_today: prev.detected_pairs_today + 1,
          last_updated: Date.now()
        }));
        // Force immediate dashboard data refresh
        window.dispatchEvent(new CustomEvent('refreshDashboard'));
        break;
      case 'position_closed':
        console.log('Position closed:', message.data);
        // Update active positions count and refresh dashboard
        setBotStatus(prev => ({ 
          ...prev, 
          active_positions: Math.max(0, prev.active_positions - 1)
        }));
        // Force dashboard refresh by updating a timestamp
        setBotStatus(prev => ({ ...prev, last_updated: Date.now() }));
        break;
      case 'positions_bulk_closed':
        console.log('Bulk positions closed:', message.data);
        setBotStatus(prev => ({ 
          ...prev, 
          active_positions: Math.max(0, prev.active_positions - message.data.closed_count)
        }));
        break;
      case 'demo_position_created':
        console.log('Demo position created:', message.data);
        setBotStatus(prev => ({ 
          ...prev, 
          active_positions: prev.active_positions + 1
        }));
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900">
      <div className="container mx-auto px-4 py-6">
        <header className="mb-6 md:mb-8">
          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700 rounded-2xl px-4 md:px-6 py-4">
            {/* Desktop Header */}
            <div className="hidden md:flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-16 h-16 rounded-xl flex items-center justify-center">
                  <img src="/paradox-logo.svg" alt="Paradox Bot" className="w-full h-full" />
                </div>
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                    Paradox Bot
                  </h1>
                  <p className="text-gray-400 text-sm">Advanced Trading Intelligence</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-8">
                {/* Current Time */}
                <div className="flex items-center space-x-2">
                  <span className="text-sm text-gray-300">
                    London: {currentTime.toLocaleTimeString('en-GB', { 
                      timeZone: 'Europe/London',
                      hour12: false 
                    })}
                  </span>
                </div>
                
                {/* Status Indicators */}
                <div className="flex items-center gap-4 px-4 py-2 bg-gray-800/30 rounded-lg border border-gray-700">
                  {/* WebSocket Status */}
                  <div className="flex items-center space-x-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${
                      isConnected 
                        ? 'bg-green-500 shadow-lg shadow-green-500/50' 
                        : isConnecting
                        ? 'bg-yellow-500 shadow-lg shadow-yellow-500/50 animate-pulse'
                        : 'bg-red-500 shadow-lg shadow-red-500/50'
                    }`}></div>
                    <span className="text-xs text-gray-300 whitespace-nowrap">
                      WS: {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Error'}
                    </span>
                  </div>
                  
                  {/* Blockchain Status */}
                  <div className="flex items-center space-x-2">
                    <div className={`w-2.5 h-2.5 rounded-full ${
                      botStatus.blockchain_connected 
                        ? 'bg-green-500 shadow-lg shadow-green-500/50' 
                        : 'bg-red-500 shadow-lg shadow-red-500/50'
                    }`}></div>
                    <span className="text-xs text-gray-300 whitespace-nowrap">
                      BC: {botStatus.blockchain_connected ? 'Connected' : 'Error'}
                    </span>
                  </div>
                  
                  {/* Bot Status */}
                  <div className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                    botStatus.is_running 
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                  }`}>
                    {botStatus.is_running ? 'RUNNING' : 'STOPPED'}
                  </div>
                </div>
              </div>
            </div>
            
            {/* Mobile Header */}
            <div className="md:hidden">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center">
                    <img src="/paradox-logo.svg" alt="Paradox Bot" className="w-full h-full" />
                  </div>
                  <div>
                    <h1 className="text-base font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                      Paradox Bot
                    </h1>
                    <p className="text-gray-400 text-xs">DeFi Trading</p>
                  </div>
                </div>
                
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                  botStatus.is_running 
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
                }`}>
                  {botStatus.is_running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
              
              {/* Mobile Status Indicators */}
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-800/30 rounded border border-gray-700">
                  <div className={`w-2 h-2 rounded-full ${
                    isConnected 
                      ? 'bg-green-500 shadow-sm shadow-green-500/50' 
                      : isConnecting
                      ? 'bg-yellow-500 shadow-sm shadow-yellow-500/50 animate-pulse'
                      : 'bg-red-500 shadow-sm shadow-red-500/50'
                  }`}></div>
                  <span className="text-gray-300 text-xs">WS</span>
                </div>
                <div className="flex items-center gap-1.5 px-2 py-1 bg-gray-800/30 rounded border border-gray-700">
                  <div className={`w-2 h-2 rounded-full ${
                    botStatus.blockchain_connected 
                      ? 'bg-green-500 shadow-sm shadow-green-500/50' 
                      : 'bg-red-500 shadow-sm shadow-red-500/50'
                  }`}></div>
                  <span className="text-gray-300 text-xs">BC</span>
                </div>
              </div>
              
              <div className="text-right">
                {!isConnected && (
                  <button 
                    onClick={() => window.location.reload()} 
                    className="text-xs text-blue-400 hover:text-blue-300 underline"
                  >
                    Reconnect
                  </button>
                )}
                <div className="text-gray-400 text-xs">
                  Block: {botStatus.last_block?.toLocaleString() || 'N/A'}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Navigation Menu - Mobile Responsive */}
        <nav className="mb-8">
          <div className="bg-gray-800/50 backdrop-blur-xl border border-gray-700 rounded-2xl p-2">
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center justify-center">
              <div className="flex space-x-1">
                <NavButton href="/" label="Dashboard" icon={LayoutDashboard} />
                <NavButton href="/sniper" label="Paradox Control" icon={Zap} />
                <NavButton href="/positions" label="Positions" icon={Briefcase} />
                <NavButton href="/config" label="Configuration" icon={Settings} />
                <NavButton href="/wallets" label="Wallets" icon={Wallet} />
              </div>
            </div>
            
            {/* Mobile Navigation */}
            <div className="flex md:hidden flex-wrap gap-2 justify-center">
              <NavButton href="/" label="Dashboard" mobileLabel="Dashboard" icon={LayoutDashboard} />
              <NavButton href="/sniper" label="Paradox" mobileLabel="Paradox" icon={Zap} />
              <NavButton href="/positions" label="Positions" mobileLabel="Positions" icon={Briefcase} />
              <NavButton href="/config" label="Config" mobileLabel="Config" icon={Settings} />
              <NavButton href="/wallets" label="Wallets" mobileLabel="Wallets" icon={Wallet} />
            </div>
          </div>
        </nav>

        <Routes>
          <Route path="/" element={
            <Dashboard 
              botStatus={botStatus} 
              isConnected={isConnected}
              ws={ws}
              refreshTrigger={Date.now()} // Force refresh when props change
            />
          } />
          <Route path="/sniper" element={<SniperControl botStatus={botStatus} />} />
          <Route path="/positions" element={<PositionsView ws={ws} />} />
          <Route path="/config" element={<ConfigPanel />} />
          <Route path="/wallets" element={<WalletManager ws={ws} />} />
        </Routes>
      </div>
      
      <Toaster position="top-right" />
    </div>
  );
};

// Main App Component
function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;