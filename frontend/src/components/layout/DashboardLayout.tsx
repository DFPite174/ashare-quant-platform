import React from 'react';
import { useSelector } from 'react-redux';
import { selectCurrentTab } from '../../store/slices/aiStrategySlice';
import { ModuleGrid } from './ModuleGrid';
import { NewBacktestCenterPage } from '../../pages/NewBacktestCenterPage';
import { MarketWeatherBackground } from './MarketWeatherBackground';
import { RouteFallback } from '../common/UnifiedLoading';

const UserCenterPage = React.lazy(() => import('../../features/user-center/pages/UserCenterPage'));
const RealTradingPage = React.lazy(() => import('../../pages/trading/RealTradingPage'));
const QuantBotPage = React.lazy(() => import('../../features/quantbot/pages/QuantBotPage'));

interface DashboardLayoutProps {
  modules: any[];
  onLayoutChange: (layout: any[]) => void;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ modules, onLayoutChange }) => {
  const activeTab = useSelector(selectCurrentTab);

  const renderContent = () => {
    switch (activeTab as any) {
      case 'dashboard':
        return <ModuleGrid modules={modules} onLayoutChange={onLayoutChange} />;
      case 'backtest':
        return (
          <div className="w-full h-full">
            <NewBacktestCenterPage />
          </div>
        );
      case 'agent':
        return (
          <React.Suspense fallback={<RouteFallback message="加载 QuantBot..." />}>
            <div className="w-full h-full flex items-center justify-center">
              <QuantBotPage />
            </div>
          </React.Suspense>
        );
      case 'trading':
        return (
          <React.Suspense fallback={<RouteFallback message="加载交易..." />}>
            <div className="w-full h-full">
              <RealTradingPage />
            </div>
          </React.Suspense>
        );
      case 'profile':
        return (
          <React.Suspense fallback={<RouteFallback message="加载个人中心..." />}>
            <div className="w-full h-full flex items-center justify-center">
              <UserCenterPage />
            </div>
          </React.Suspense>
        );
      default:
        return <ModuleGrid modules={modules} onLayoutChange={onLayoutChange} />;
    }
  };

  const showWeatherBackground = activeTab === 'dashboard';

  return (
    <div className="dashboard-layout w-full h-full p-0 relative z-0">
      {showWeatherBackground && <MarketWeatherBackground />}
      <div className="relative z-10 h-full w-full">{renderContent()}</div>
    </div>
  );
};
