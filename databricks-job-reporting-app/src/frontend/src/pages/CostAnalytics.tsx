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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
} from '@mui/material';
import {
  AttachMoney as MoneyIcon,
  TrendingUp as TrendingIcon,
  WorkHistory as JobsIcon,
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
} from 'recharts';
import {
  getCostSummary,
  getDailyCosts,
  getTopExpensiveJobs,
  getCostByIdentity,
} from '../services/api';
import type { CostSummary } from '../types';

const COLORS = ['#FF3621', '#2196f3', '#4caf50', '#ff9800', '#9c27b0', '#00bcd4', '#e91e63', '#607d8b'];

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
}) => (
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
              <Skeleton width={100} height={40} />
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

const CostAnalytics: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [costSummary, setCostSummary] = useState<CostSummary | null>(null);
  const [dailyCosts, setDailyCosts] = useState<any[]>([]);
  const [topJobs, setTopJobs] = useState<any[]>([]);
  const [costByIdentity, setCostByIdentity] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [summary, daily, jobs, identity] = await Promise.all([
          getCostSummary(days),
          getDailyCosts(days),
          getTopExpensiveJobs(days, 10),
          getCostByIdentity(days),
        ]);
        setCostSummary(summary);
        setDailyCosts(daily);
        setTopJobs(jobs);
        setCostByIdentity(identity);
      } catch (error) {
        console.error('Failed to fetch cost data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [days]);

  const avgDailyCost = costSummary
    ? costSummary.total_cost_usd / Math.min(days, dailyCosts.length || 1)
    : 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Cost Analytics
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Track and analyze your Databricks job costs
          </Typography>
        </Box>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Time Range</InputLabel>
          <Select
            value={days}
            label="Time Range"
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <MenuItem value={7}>Last 7 Days</MenuItem>
            <MenuItem value={14}>Last 14 Days</MenuItem>
            <MenuItem value={30}>Last 30 Days</MenuItem>
            <MenuItem value={60}>Last 60 Days</MenuItem>
            <MenuItem value={90}>Last 90 Days</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Cost"
            value={`$${(costSummary?.total_cost_usd || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle={`Last ${days} days`}
            icon={<MoneyIcon />}
            color="#9c27b0"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Avg Daily Cost"
            value={`$${avgDailyCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            icon={<TrendingIcon />}
            color="#2196f3"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total DBUs"
            value={(costSummary?.total_dbus || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            icon={<TrendingIcon />}
            color="#4caf50"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Unique Jobs"
            value={costSummary?.unique_jobs || 0}
            subtitle={`${costSummary?.total_runs || 0} total runs`}
            icon={<JobsIcon />}
            color="#ff9800"
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Charts Row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Daily Cost Trend */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Daily Cost Trend
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={320} />
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={dailyCosts}>
                  <defs>
                    <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#9c27b0" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#9c27b0" stopOpacity={0} />
                    </linearGradient>
                  </defs>
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
                  <Area
                    type="monotone"
                    dataKey="cost_usd"
                    stroke="#9c27b0"
                    fillOpacity={1}
                    fill="url(#colorCost)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Cost by Identity */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 400 }}>
            <Typography variant="h6" gutterBottom>
              Cost by Identity
            </Typography>
            {loading ? (
              <Skeleton variant="circular" width={280} height={280} sx={{ mx: 'auto' }} />
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <PieChart>
                  <Pie
                    data={costByIdentity.slice(0, 8)}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="cost_usd"
                    nameKey="identity"
                    label={({ percent }) =>
                      percent > 0.05 ? `${(percent * 100).toFixed(0)}%` : ''
                    }
                  >
                    {costByIdentity.slice(0, 8).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Top Expensive Jobs */}
      <Grid container spacing={3}>
        <Grid item xs={12} lg={7}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Top 10 Most Expensive Jobs
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : (
              <TableContainer sx={{ maxHeight: 400 }}>
                <Table stickyHeader size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Rank</TableCell>
                      <TableCell>Job Name</TableCell>
                      <TableCell align="right">Total Cost</TableCell>
                      <TableCell align="right">Runs</TableCell>
                      <TableCell align="right">Avg Cost/Run</TableCell>
                      <TableCell align="right">DBUs</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {topJobs.map((job, index) => (
                      <TableRow key={job.job_id} hover>
                        <TableCell>
                          <Chip
                            label={index + 1}
                            size="small"
                            color={index < 3 ? 'warning' : 'default'}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {job.job_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.job_id}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography
                            variant="body2"
                            fontWeight={600}
                            color={index < 3 ? 'warning.main' : 'text.primary'}
                          >
                            ${job.total_cost.toFixed(2)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">{job.total_runs}</TableCell>
                        <TableCell align="right">
                          ${(job.total_cost / job.total_runs).toFixed(2)}
                        </TableCell>
                        <TableCell align="right">
                          {job.total_dbus?.toFixed(1) || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} lg={5}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 'calc(100% - 24px)' }}>
            <Typography variant="h6" gutterBottom>
              Cost Distribution
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={350} />
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <BarChart
                  data={topJobs.slice(0, 8)}
                  layout="vertical"
                  margin={{ left: 120, right: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis type="number" stroke="#888" tickFormatter={(v) => `$${v}`} />
                  <YAxis
                    type="category"
                    dataKey="job_name"
                    stroke="#888"
                    tick={{ fontSize: 11 }}
                    width={110}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                  />
                  <Bar dataKey="total_cost" radius={[0, 4, 4, 0]}>
                    {topJobs.slice(0, 8).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CostAnalytics;
