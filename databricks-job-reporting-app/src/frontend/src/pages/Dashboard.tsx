import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Skeleton,
  Chip,
  LinearProgress,
  useTheme,
} from '@mui/material';
import {
  CheckCircle as SuccessIcon,
  Error as FailedIcon,
  PlayArrow as RunningIcon,
  Schedule as TotalIcon,
  TrendingUp as TrendUpIcon,
  AttachMoney as CostIcon,
} from '@mui/icons-material';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import {
  getRunSummary,
  getDailyRuns,
  getCostSummary,
  getJobRunsByType,
  getDailyCosts,
} from '../services/api';
import type { RunSummary, CostSummary } from '../types';

const COLORS = ['#4caf50', '#f44336', '#2196f3', '#ff9800', '#9c27b0'];

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  loading?: boolean;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color,
  loading,
}) => {
  const theme = useTheme();
  return (
    <motion.div whileHover={{ scale: 1.02 }} transition={{ duration: 0.2 }}>
      <Card
        sx={{
          background: `linear-gradient(135deg, ${color}15 0%, ${color}05 100%)`,
          border: `1px solid ${color}30`,
          borderRadius: 3,
          height: '100%',
        }}
      >
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {title}
              </Typography>
              {loading ? (
                <Skeleton width={80} height={40} />
              ) : (
                <Typography variant="h4" fontWeight="bold" sx={{ color }}>
                  {value}
                </Typography>
              )}
              {subtitle && (
                <Typography variant="caption" color="text.secondary">
                  {subtitle}
                </Typography>
              )}
            </Box>
            <Box
              sx={{
                p: 1,
                borderRadius: 2,
                bgcolor: `${color}20`,
                color,
              }}
            >
              {icon}
            </Box>
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
};

const Dashboard: React.FC = () => {
  const theme = useTheme();
  const [loading, setLoading] = useState(true);
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [dailyRuns, setDailyRuns] = useState<any[]>([]);
  const [dailyCosts, setDailyCosts] = useState<any[]>([]);
  const [jobsByType, setJobsByType] = useState<Record<string, number>>({});

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [runs, costs, daily, costDaily, types] = await Promise.all([
          getRunSummary(7),
          getCostSummary(30),
          getDailyRuns(14),
          getDailyCosts(14),
          getJobRunsByType(7),
        ]);
        setRunSummary(runs);
        setCostSummary(costs);
        setDailyRuns(daily);
        setDailyCosts(costDaily);
        setJobsByType(types);
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const typeChartData = Object.entries(jobsByType).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Dashboard Overview
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor your Databricks jobs performance and costs at a glance
        </Typography>
      </Box>

      {/* Metric Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Runs (7d)"
            value={runSummary?.total_runs?.toLocaleString() || 0}
            icon={<TotalIcon />}
            color={theme.palette.info.main}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Succeeded"
            value={runSummary?.succeeded?.toLocaleString() || 0}
            subtitle={`${(runSummary?.success_rate || 0).toFixed(1)}% success rate`}
            icon={<SuccessIcon />}
            color={theme.palette.success.main}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Failed"
            value={runSummary?.failed?.toLocaleString() || 0}
            icon={<FailedIcon />}
            color={theme.palette.error.main}
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Running"
            value={runSummary?.running?.toLocaleString() || 0}
            icon={<RunningIcon />}
            color={theme.palette.warning.main}
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Cost Overview */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total Cost (30d)"
            value={`$${(costSummary?.total_cost_usd || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            icon={<CostIcon />}
            color="#9c27b0"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total DBUs"
            value={(costSummary?.total_dbus || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            icon={<TrendUpIcon />}
            color="#00bcd4"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Unique Jobs"
            value={costSummary?.unique_jobs || 0}
            subtitle={`${costSummary?.total_runs || 0} total runs`}
            icon={<TotalIcon />}
            color="#ff5722"
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3}>
        {/* Daily Runs Chart */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Daily Job Runs
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={320} />
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={dailyRuns}>
                  <defs>
                    <linearGradient id="colorSucceeded" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4caf50" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#4caf50" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f44336" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#f44336" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" stroke="#888" />
                  <YAxis stroke="#888" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="succeeded"
                    stroke="#4caf50"
                    fillOpacity={1}
                    fill="url(#colorSucceeded)"
                  />
                  <Area
                    type="monotone"
                    dataKey="failed"
                    stroke="#f44336"
                    fillOpacity={1}
                    fill="url(#colorFailed)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Job Types Pie Chart */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Jobs by Run Type
            </Typography>
            {loading ? (
              <Skeleton variant="circular" width={280} height={280} sx={{ mx: 'auto' }} />
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={typeChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {typeChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Daily Costs Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Daily Costs (Last 14 Days)
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={320} />
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={dailyCosts}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="date" stroke="#888" />
                  <YAxis stroke="#888" tickFormatter={(value) => `$${value}`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                  />
                  <Bar dataKey="cost_usd" fill="#9c27b0" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
