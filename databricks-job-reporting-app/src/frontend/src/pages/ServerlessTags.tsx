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
  LinearProgress,
  Alert,
  Tabs,
  Tab,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  LocalOffer as TagIcon,
  Business as BusinessIcon,
  AccountTree as PipelineIcon,
  TrendingUp as TrendingIcon,
  Assessment as AssessmentIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
  LineChart,
  Line,
} from 'recharts';
import {
  getServerlessTagSummary,
  getServerlessCostByTags,
  getServerlessCostTrends,
  getUnmatchedRuns,
  getTagPolicies,
} from '../services/api';
import type {
  ServerlessTagSummary,
  ServerlessCostByTag,
  ServerlessCostTrend,
  UnmatchedRun,
  TagPolicy,
} from '../types';

const COLORS = ['#FF3621', '#2196f3', '#4caf50', '#ff9800', '#9c27b0', '#00bcd4', '#e91e63', '#607d8b'];

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  loading?: boolean;
  progress?: number;
}

const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  color,
  loading,
  progress,
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
          <Box sx={{ flex: 1 }}>
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
            {progress !== undefined && (
              <Box sx={{ mt: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={progress}
                  sx={{
                    height: 6,
                    borderRadius: 3,
                    bgcolor: `${color}20`,
                    '& .MuiLinearProgress-bar': {
                      bgcolor: color,
                    },
                  }}
                />
              </Box>
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

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div role="tabpanel" hidden={value !== index}>
    {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
  </div>
);

const ServerlessTags: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [tabValue, setTabValue] = useState(0);
  const [summary, setSummary] = useState<ServerlessTagSummary | null>(null);
  const [costByTags, setCostByTags] = useState<ServerlessCostByTag[]>([]);
  const [costTrends, setCostTrends] = useState<ServerlessCostTrend[]>([]);
  const [unmatchedRuns, setUnmatchedRuns] = useState<UnmatchedRun[]>([]);
  const [tagPolicies, setTagPolicies] = useState<TagPolicy[]>([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [summaryData, costData, trendsData, unmatchedData, policiesData] = await Promise.all([
        getServerlessTagSummary(days),
        getServerlessCostByTags(days),
        getServerlessCostTrends(days),
        getUnmatchedRuns(days, 50),
        getTagPolicies(),
      ]);
      setSummary(summaryData);
      setCostByTags(costData);
      setCostTrends(trendsData);
      setUnmatchedRuns(unmatchedData);
      setTagPolicies(policiesData);
    } catch (error) {
      console.error('Failed to fetch serverless tag data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [days]);

  const correlationRate = summary?.correlation_rate || 0;

  // Prepare data for charts
  const departmentData = costByTags
    .filter((item) => item.department)
    .reduce((acc, item) => {
      const existing = acc.find((a) => a.department === item.department);
      if (existing) {
        existing.cost_usd += item.cost_usd;
      } else {
        acc.push({ department: item.department, cost_usd: item.cost_usd });
      }
      return acc;
    }, [] as { department: string; cost_usd: number }[])
    .sort((a, b) => b.cost_usd - a.cost_usd)
    .slice(0, 8);

  const projectData = costByTags
    .filter((item) => item.project_code)
    .reduce((acc, item) => {
      const existing = acc.find((a) => a.project_code === item.project_code);
      if (existing) {
        existing.cost_usd += item.cost_usd;
      } else {
        acc.push({ project_code: item.project_code, cost_usd: item.cost_usd });
      }
      return acc;
    }, [] as { project_code: string; cost_usd: number }[])
    .sort((a, b) => b.cost_usd - a.cost_usd)
    .slice(0, 10);

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Serverless Tags & Cost Attribution
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Dynamic tag correlation for serverless compute cost tracking
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Tooltip title="Refresh Data">
            <IconButton onClick={fetchData} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
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
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Tag Correlation Rate"
            value={`${correlationRate.toFixed(1)}%`}
            subtitle={correlationRate >= 80 ? 'Good coverage' : 'Needs improvement'}
            icon={correlationRate >= 80 ? <CheckCircleIcon /> : <WarningIcon />}
            color={correlationRate >= 80 ? '#4caf50' : '#ff9800'}
            loading={loading}
            progress={correlationRate}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Tagged Cost"
            value={`$${(summary?.total_tagged_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle={`${summary?.total_tagged_runs || 0} tagged runs`}
            icon={<TagIcon />}
            color="#9c27b0"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Unique Projects"
            value={summary?.unique_projects || 0}
            subtitle={`${summary?.unique_departments || 0} departments`}
            icon={<PipelineIcon />}
            color="#2196f3"
            loading={loading}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Untagged Runs"
            value={summary?.unmatched_runs || 0}
            subtitle={`$${(summary?.unmatched_cost || 0).toLocaleString()} unattributed`}
            icon={<WarningIcon />}
            color="#f44336"
            loading={loading}
          />
        </Grid>
      </Grid>

      {/* Tabs */}
      <Paper sx={{ borderRadius: 3, mb: 3 }}>
        <Tabs
          value={tabValue}
          onChange={(_, newValue) => setTabValue(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}
        >
          <Tab label="Cost Attribution" icon={<AssessmentIcon />} iconPosition="start" />
          <Tab label="Cost Trends" icon={<TrendingIcon />} iconPosition="start" />
          <Tab label="Unmatched Runs" icon={<WarningIcon />} iconPosition="start" />
          <Tab label="Tag Policies" icon={<TagIcon />} iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Tab Panel: Cost Attribution */}
      <TabPanel value={tabValue} index={0}>
        <Grid container spacing={3}>
          {/* Cost by Department */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 450 }}>
              <Typography variant="h6" gutterBottom>
                Cost by Department
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={380} />
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <PieChart>
                    <Pie
                      data={departmentData}
                      cx="50%"
                      cy="50%"
                      innerRadius={80}
                      outerRadius={140}
                      paddingAngle={2}
                      dataKey="cost_usd"
                      nameKey="department"
                      label={({ department, percent }) =>
                        percent > 0.05 ? `${department}: ${(percent * 100).toFixed(0)}%` : ''
                      }
                    >
                      {departmentData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                      formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </Paper>
          </Grid>

          {/* Cost by Project */}
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 450 }}>
              <Typography variant="h6" gutterBottom>
                Top Projects by Cost
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={380} />
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <BarChart
                    data={projectData}
                    layout="vertical"
                    margin={{ left: 100, right: 20 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis type="number" stroke="#888" tickFormatter={(v) => `$${v}`} />
                    <YAxis
                      type="category"
                      dataKey="project_code"
                      stroke="#888"
                      tick={{ fontSize: 11 }}
                      width={90}
                    />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                      formatter={(value: number) => [`$${value.toFixed(2)}`, 'Cost']}
                    />
                    <Bar dataKey="cost_usd" radius={[0, 4, 4, 0]}>
                      {projectData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Paper>
          </Grid>

          {/* Detailed Cost Table */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3, borderRadius: 3 }}>
              <Typography variant="h6" gutterBottom>
                Cost Attribution Details
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={400} />
              ) : (
                <TableContainer sx={{ maxHeight: 400 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Project Code</TableCell>
                        <TableCell>Department</TableCell>
                        <TableCell>Business Unit</TableCell>
                        <TableCell>Environment</TableCell>
                        <TableCell align="right">Total Cost</TableCell>
                        <TableCell align="right">Runs</TableCell>
                        <TableCell align="right">Correlation %</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {costByTags.slice(0, 20).map((item, index) => (
                        <TableRow key={index} hover>
                          <TableCell>
                            <Chip
                              label={item.project_code || 'N/A'}
                              size="small"
                              color={item.project_code ? 'primary' : 'default'}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>{item.department || '-'}</TableCell>
                          <TableCell>{item.business_unit || '-'}</TableCell>
                          <TableCell>
                            <Chip
                              label={item.environment || 'N/A'}
                              size="small"
                              color={
                                item.environment === 'prod'
                                  ? 'error'
                                  : item.environment === 'staging'
                                  ? 'warning'
                                  : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight={600}>
                              ${item.cost_usd.toFixed(2)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">{item.run_count}</TableCell>
                          <TableCell align="right">
                            <Chip
                              label={`${item.correlation_quality.toFixed(0)}%`}
                              size="small"
                              color={item.correlation_quality >= 80 ? 'success' : 'warning'}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Tab Panel: Cost Trends */}
      <TabPanel value={tabValue} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 450 }}>
              <Typography variant="h6" gutterBottom>
                Weekly Cost Trends
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={380} />
              ) : (
                <ResponsiveContainer width="100%" height={380}>
                  <AreaChart data={costTrends}>
                    <defs>
                      <linearGradient id="colorTaggedCost" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#4caf50" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#4caf50" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorUntaggedCost" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f44336" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#f44336" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="week" stroke="#888" />
                    <YAxis stroke="#888" tickFormatter={(value) => `$${value}`} />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                      formatter={(value: number) => [`$${value.toFixed(2)}`]}
                    />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="tagged_cost"
                      name="Tagged Cost"
                      stroke="#4caf50"
                      fillOpacity={1}
                      fill="url(#colorTaggedCost)"
                    />
                    <Area
                      type="monotone"
                      dataKey="untagged_cost"
                      name="Untagged Cost"
                      stroke="#f44336"
                      fillOpacity={1}
                      fill="url(#colorUntaggedCost)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
              <Typography variant="h6" gutterBottom>
                Correlation Rate Over Time
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={280} />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={costTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="week" stroke="#888" />
                    <YAxis stroke="#888" domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                      formatter={(value: number) => [`${value.toFixed(1)}%`, 'Correlation Rate']}
                    />
                    <Line
                      type="monotone"
                      dataKey="correlation_rate"
                      name="Correlation Rate"
                      stroke="#2196f3"
                      strokeWidth={2}
                      dot={{ fill: '#2196f3', strokeWidth: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
              <Typography variant="h6" gutterBottom>
                Week-over-Week Variance
              </Typography>
              {loading ? (
                <Skeleton variant="rectangular" height={280} />
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={costTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                    <XAxis dataKey="week" stroke="#888" />
                    <YAxis stroke="#888" tickFormatter={(v) => `${v}%`} />
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                      formatter={(value: number) => [`${value.toFixed(1)}%`, 'WoW Change']}
                    />
                    <Bar dataKey="wow_variance" name="WoW Variance">
                      {costTrends.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.wow_variance >= 0 ? '#f44336' : '#4caf50'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Tab Panel: Unmatched Runs */}
      <TabPanel value={tabValue} index={2}>
        {unmatchedRuns.length === 0 ? (
          <Alert severity="success" sx={{ borderRadius: 2 }}>
            All serverless runs have been successfully tagged! Great job maintaining cost attribution.
          </Alert>
        ) : (
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Unmatched Serverless Runs ({unmatchedRuns.length})
              </Typography>
              <Alert severity="warning" sx={{ py: 0 }}>
                These runs lack tag correlations and cannot be attributed to projects/departments
              </Alert>
            </Box>
            <TableContainer sx={{ maxHeight: 500 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Job ID</TableCell>
                    <TableCell>Run ID</TableCell>
                    <TableCell>Notebook Path</TableCell>
                    <TableCell>Start Time</TableCell>
                    <TableCell align="right">Duration (min)</TableCell>
                    <TableCell align="right">Est. Cost</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {unmatchedRuns.map((run, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {run.job_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {run.run_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip title={run.notebook_path || ''}>
                          <Typography
                            variant="body2"
                            sx={{
                              maxWidth: 200,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {run.notebook_path || '-'}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      <TableCell>
                        {new Date(run.start_time).toLocaleString()}
                      </TableCell>
                      <TableCell align="right">
                        {run.duration_minutes?.toFixed(1) || '-'}
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" color="warning.main" fontWeight={600}>
                          ${run.estimated_cost?.toFixed(2) || '0.00'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={run.run_status}
                          size="small"
                          color={
                            run.run_status === 'SUCCESS'
                              ? 'success'
                              : run.run_status === 'FAILED'
                              ? 'error'
                              : 'default'
                          }
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        )}
      </TabPanel>

      {/* Tab Panel: Tag Policies */}
      <TabPanel value={tabValue} index={3}>
        <Paper sx={{ p: 3, borderRadius: 3 }}>
          <Typography variant="h6" gutterBottom>
            Tag Policy Definitions
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Configure validation rules for serverless compute tags
          </Typography>
          {loading ? (
            <Skeleton variant="rectangular" height={400} />
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Tag Key</TableCell>
                    <TableCell>Display Name</TableCell>
                    <TableCell>Category</TableCell>
                    <TableCell>Required</TableCell>
                    <TableCell>Allowed Values</TableCell>
                    <TableCell>Validation Pattern</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tagPolicies.map((policy, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                          {policy.tag_key}
                        </Typography>
                      </TableCell>
                      <TableCell>{policy.tag_display_name}</TableCell>
                      <TableCell>
                        <Chip label={policy.tag_category} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        {policy.is_required ? (
                          <Chip label="Required" size="small" color="error" />
                        ) : (
                          <Chip label="Optional" size="small" color="default" />
                        )}
                      </TableCell>
                      <TableCell>
                        {policy.allowed_values?.length ? (
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {policy.allowed_values.slice(0, 3).map((val, i) => (
                              <Chip key={i} label={val} size="small" variant="outlined" />
                            ))}
                            {policy.allowed_values.length > 3 && (
                              <Chip label={`+${policy.allowed_values.length - 3}`} size="small" />
                            )}
                          </Box>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            Any value
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace" fontSize={11}>
                          {policy.validation_regex || '-'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={policy.is_active ? 'Active' : 'Inactive'}
                          size="small"
                          color={policy.is_active ? 'success' : 'default'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </TabPanel>
    </Box>
  );
};

export default ServerlessTags;
