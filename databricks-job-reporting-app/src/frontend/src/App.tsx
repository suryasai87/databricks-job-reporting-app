import React, { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Chip,
  Tooltip,
  Divider,
  useTheme,
  CircularProgress,
} from '@mui/material';
import {
  Menu as MenuIcon,
  ChevronLeft as ChevronLeftIcon,
  Dashboard as DashboardIcon,
  WorkHistory as JobsIcon,
  AttachMoney as CostIcon,
  HealthAndSafety as HealthIcon,
  SmartToy as AIIcon,
  Assessment as ReportsIcon,
  Settings as SettingsIcon,
  Api as ApiIcon,
  Schedule as ScheduleIcon,
  BubbleChart as ClusterIcon,
} from '@mui/icons-material';
import type { User } from './types';
import { getAuthStatus } from './services/api';

// Pages
import Dashboard from './pages/Dashboard';
import JobsList from './pages/JobsList';
import CostAnalytics from './pages/CostAnalytics';
import Health from './pages/Health';
import AIAssistant from './pages/AIAssistant';
import Reports from './pages/Reports';
import GanttView from './pages/GanttView';
import ClusterAnalysis from './pages/ClusterAnalysis';
import Settings from './pages/Settings';

const drawerWidth = 280;
const miniDrawerWidth = 72;

const navItems = [
  { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
  { path: '/jobs', label: 'Jobs List', icon: <JobsIcon /> },
  { path: '/gantt', label: 'Gantt View', icon: <ScheduleIcon /> },
  { path: '/costs', label: 'Cost Analytics', icon: <CostIcon /> },
  { path: '/health', label: 'Health & Anomalies', icon: <HealthIcon /> },
  { path: '/clusters', label: 'Cluster Analysis', icon: <ClusterIcon /> },
  { path: '/ai-assistant', label: 'AI Assistant', icon: <AIIcon /> },
  { path: '/reports', label: 'Reports', icon: <ReportsIcon /> },
  { path: '/settings', label: 'Settings', icon: <SettingsIcon /> },
];

const App: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const userData = await getAuthStatus();
        setUser(userData);
      } catch (error) {
        console.error('Failed to fetch user:', error);
        setUser({ email: 'anonymous', source: 'none', authenticated: false });
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  const toggleDrawer = () => {
    setDrawerOpen(!drawerOpen);
  };

  const currentWidth = drawerOpen ? drawerWidth : miniDrawerWidth;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          zIndex: theme.zIndex.drawer + 1,
          background: 'linear-gradient(90deg, #1a1a2e 0%, #16213e 100%)',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            onClick={toggleDrawer}
            edge="start"
            sx={{ mr: 2 }}
          >
            {drawerOpen ? <ChevronLeftIcon /> : <MenuIcon />}
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Databricks Jobs Monitor
          </Typography>
          <Tooltip title="API Documentation">
            <IconButton
              color="inherit"
              onClick={() => window.open('/docs', '_blank')}
              sx={{ mr: 2 }}
            >
              <ApiIcon />
            </IconButton>
          </Tooltip>
          {loading ? (
            <CircularProgress size={24} color="inherit" />
          ) : user?.authenticated ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip
                label={user.source.toUpperCase()}
                size="small"
                color="success"
                variant="outlined"
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.5)' }}
              />
              <Avatar sx={{ bgcolor: theme.palette.primary.main, width: 32, height: 32 }}>
                {user.email?.[0]?.toUpperCase() || 'U'}
              </Avatar>
              <Typography variant="body2" sx={{ color: 'white' }}>
                {user.name || user.email}
              </Typography>
            </Box>
          ) : (
            <Chip label="Not Authenticated" color="warning" size="small" />
          )}
        </Toolbar>
      </AppBar>

      {/* Drawer */}
      <Drawer
        variant="permanent"
        sx={{
          width: currentWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: currentWidth,
            boxSizing: 'border-box',
            transition: theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
            overflowX: 'hidden',
            background: 'linear-gradient(180deg, #1a1a2e 0%, #0f0f1a 100%)',
            borderRight: '1px solid rgba(255,255,255,0.1)',
          },
        }}
      >
        <Toolbar />
        <Box sx={{ py: 2 }}>
          <List>
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <ListItem key={item.path} disablePadding sx={{ mb: 0.5, px: 1 }}>
                  <motion.div
                    style={{ width: '100%' }}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <ListItemButton
                      onClick={() => navigate(item.path)}
                      sx={{
                        borderRadius: 2,
                        bgcolor: isActive ? 'rgba(255, 54, 33, 0.15)' : 'transparent',
                        '&:hover': {
                          bgcolor: isActive
                            ? 'rgba(255, 54, 33, 0.2)'
                            : 'rgba(255,255,255,0.05)',
                        },
                        minHeight: 48,
                        justifyContent: drawerOpen ? 'initial' : 'center',
                        px: 2.5,
                      }}
                    >
                      <ListItemIcon
                        sx={{
                          minWidth: 0,
                          mr: drawerOpen ? 2 : 'auto',
                          justifyContent: 'center',
                          color: isActive ? 'primary.main' : 'grey.400',
                        }}
                      >
                        {item.icon}
                      </ListItemIcon>
                      <AnimatePresence>
                        {drawerOpen && (
                          <motion.div
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            transition={{ duration: 0.2 }}
                          >
                            <ListItemText
                              primary={item.label}
                              sx={{
                                '& .MuiListItemText-primary': {
                                  color: isActive ? 'primary.main' : 'grey.300',
                                  fontWeight: isActive ? 600 : 400,
                                },
                              }}
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </ListItemButton>
                  </motion.div>
                </ListItem>
              );
            })}
          </List>
          <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.1)' }} />
          {drawerOpen && (
            <Box sx={{ px: 3, py: 1 }}>
              <Typography variant="caption" color="grey.500">
                Powered by Databricks System Tables
              </Typography>
            </Box>
          )}
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: 8,
          ml: 0,
          transition: theme.transitions.create('margin', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.enteringScreen,
          }),
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/jobs" element={<JobsList />} />
              <Route path="/gantt" element={<GanttView />} />
              <Route path="/costs" element={<CostAnalytics />} />
              <Route path="/health" element={<Health />} />
              <Route path="/clusters" element={<ClusterAnalysis />} />
              <Route path="/ai-assistant" element={<AIAssistant />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </Box>
    </Box>
  );
};

export default App;
