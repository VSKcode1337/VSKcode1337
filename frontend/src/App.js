import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
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
const NavButton = ({ href, label, mobileLabel }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isActive = location.pathname === href;
  
  return (
    <button
      onClick={() => navigate(href)}
      className={`px-3 md:px-6 py-2 md:py-3 rounded-xl font-medium transition-all duration-200 text-sm md:text-base flex flex-col md:flex-row items-center gap-1 md:gap-0 ${
        isActive 
          ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25' 
          : 'text-gray-300 hover:text-white hover:bg-gray-700/50'
      }`}
      data-testid={`nav-${href.replace('/', '') || 'dashboard'}`}
    >
      <span className="text-base md:text-lg">{label.split(' ')[0]}</span>
      <span className="hidden md:inline">{label.split(' ').slice(1).join(' ')}</span>
      <span className="text-xs md:hidden">{mobileLabel}</span>
    </button>
  );
};

// Main App Content Component
const AppContent = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [botStatus, setBotStatus] = useState({
    is_running: false,
    connected_clients: 0,
    active_positions: 0,
    detected_pairs_today: 0,
    blockchain_connected: false,
    last_block: null
  });
  const [ws, setWs] = useState(null);

  // Initialize WebSocket connection
  useEffect(() => {
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    
    const connectWebSocket = () => {
      try {
        const wsUrl = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';
        console.log('Connecting to WebSocket:', wsUrl);
        const websocket = new WebSocket(wsUrl);

        websocket.onopen = () => {
          console.log('WebSocket connected successfully');
          setIsConnected(true);
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
          setWs(null);
          
          // Try to reconnect if under max attempts
          if (reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            console.log(`Reconnect attempt ${reconnectAttempts}/${maxReconnectAttempts} in 3 seconds...`);
            setTimeout(connectWebSocket, 3000);
          } else {
            console.error('Max WebSocket reconnection attempts reached');
          }
        };

        websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          setIsConnected(false);
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        setIsConnected(false);
      }
    };

    connectWebSocket();
    
    // Cleanup on unmount
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  // Fetch bot status periodically
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(`${API}/status`);
        setBotStatus(response.data);
      } catch (error) {
        console.error('Failed to fetch bot status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 10000); // Update every 10 seconds

    return () => clearInterval(interval);
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
        // Update detected pairs count
        setBotStatus(prev => ({ 
          ...prev, 
          detected_pairs_today: prev.detected_pairs_today + 1 
        }));
        break;
      case 'position_closed':
        console.log('Position closed:', message.data);
        // Update active positions count
        setBotStatus(prev => ({ 
          ...prev, 
          active_positions: Math.max(0, prev.active_positions - 1)
        }));
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
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                  <span className="text-white font-bold text-xl">🎯</span>
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white">PCS Sniper Bot</h1>
                  <p className="text-gray-400 text-sm">High-Frequency DeFi Trading</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-6">
                {/* WebSocket Status */}
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${
                    isConnected 
                      ? 'bg-green-500 animate-pulse' 
                      : 'bg-red-500'
                  }`}></div>
                  <span className="text-sm text-gray-300">
                    WebSocket: {isConnected ? 'Connected' : 'Disconnected'}
                  </span>
                  {!isConnected && (
                    <button 
                      onClick={() => window.location.reload()} 
                      className="text-xs text-blue-400 hover:text-blue-300 underline"
                    >
                      Reconnect
                    </button>
                  )}
                </div>
                
                {/* Blockchain Status */}
                <div className="flex items-center space-x-2">
                  <div className={`w-3 h-3 rounded-full ${
                    botStatus.blockchain_connected 
                      ? 'bg-green-500 animate-pulse' 
                      : 'bg-red-500'
                  }`}></div>
                  <span className="text-sm text-gray-300">
                    Blockchain: {botStatus.blockchain_connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                
                {/* Bot Status */}
                <div className="flex items-center space-x-2">
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
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
                  <div className="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-sm">🎯</span>
                  </div>
                  <div>
                    <h1 className="text-lg font-bold text-white">PCS Sniper Bot</h1>
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
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center space-x-1">
                  <div className={`w-2 h-2 rounded-full ${
                    isConnected 
                      ? 'bg-green-500 animate-pulse' 
                      : 'bg-red-500'
                  }`}></div>
                  <span className="text-gray-300">WS: {isConnected ? 'OK' : 'ERR'}</span>
                </div>
                <div className="flex items-center space-x-1">
                  <div className={`w-2 h-2 rounded-full ${
                    botStatus.blockchain_connected 
                      ? 'bg-green-500 animate-pulse' 
                      : 'bg-red-500'
                  }`}></div>
                  <span className="text-gray-300">BC: {botStatus.blockchain_connected ? 'OK' : 'ERR'}</span>
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
              </div>>
                
                <div className="text-gray-400">
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
                <NavButton href="/" label="📊 Dashboard" />
                <NavButton href="/sniper" label="⚡ Sniper Control" />
                <NavButton href="/positions" label="💼 Positions" />
                <NavButton href="/config" label="⚙️ Configuration" />
                <NavButton href="/wallets" label="👛 Wallets" />
              </div>
            </div>
            
            {/* Mobile Navigation */}
            <div className="flex md:hidden flex-wrap gap-2 justify-center">
              <NavButton href="/" label="📊" mobileLabel="Dashboard" />
              <NavButton href="/sniper" label="⚡" mobileLabel="Sniper" />
              <NavButton href="/positions" label="💼" mobileLabel="Positions" />
              <NavButton href="/config" label="⚙️" mobileLabel="Config" />
              <NavButton href="/wallets" label="👛" mobileLabel="Wallets" />
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
          <Route path="/wallets" element={<WalletManager />} />
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