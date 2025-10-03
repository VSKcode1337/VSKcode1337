import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { CheckCircle, Clock, Target, Shield, Zap } from 'lucide-react';

const RecommendedSettings = () => {
  const settings = [
    {
      category: "Trade Size",
      setting: "$75 per trade",
      reason: "Moderate risk, good profit potential",
      icon: <Target className="h-4 w-4" />
    },
    {
      category: "Position Time", 
      setting: "20 minutes MAX",
      reason: "Quick exits, no overnight holds",
      icon: <Clock className="h-4 w-4" />
    },
    {
      category: "Take Profits",
      setting: "3x, 5x, 8x (60%, 30%, 10%)",
      reason: "Take most profit early, secure gains",
      icon: <CheckCircle className="h-4 w-4" />
    },
    {
      category: "Stop Loss",
      setting: "25% down",
      reason: "Quick cut losses, preserve capital",
      icon: <Shield className="h-4 w-4" />
    },
    {
      category: "Liquidity Filter",
      setting: "$100K+ only",
      reason: "High liquidity = safer, faster exits",
      icon: <Zap className="h-4 w-4" />
    },
    {
      category: "Tax Limits",
      setting: "3% max buy/sell",
      reason: "Avoid high-tax scam tokens",
      icon: <Shield className="h-4 w-4" />
    }
  ];

  return (
    <Card className="glass border-gray-700">
      <CardHeader>
        <CardTitle className="text-white flex items-center gap-2">
          🎯 High Win-Rate Settings Explained
        </CardTitle>
        <CardDescription className="text-gray-400">
          Why these settings give you 80%+ win rate with quick trades
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {settings.map((item, index) => (
            <div key={index} className="flex items-start gap-3 p-3 bg-gray-800/30 rounded-lg">
              <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400">
                {item.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-white text-sm">{item.category}</span>
                  <Badge variant="outline" className="text-xs">{item.setting}</Badge>
                </div>
                <p className="text-xs text-gray-400">{item.reason}</p>
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <h4 className="font-medium text-green-400 mb-2 flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            Why This Strategy Works
          </h4>
          <ul className="text-xs text-green-200/80 space-y-1">
            <li>• <strong>High Selectivity:</strong> Only trades the safest, highest-liquidity tokens</li>
            <li>• <strong>Quick Exits:</strong> No overnight risk, 20-minute maximum hold time</li>
            <li>• <strong>Early Profits:</strong> Takes 60% profit at 3x, secures gains quickly</li>
            <li>• <strong>Fast Stop-Loss:</strong> Cuts losses at 25%, preserves capital for next trade</li>
            <li>• <strong>Scam Protection:</strong> Strict tax limits avoid honeypots and rug pulls</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
};

export default RecommendedSettings;