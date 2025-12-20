import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Card,
  CardContent,
  Skeleton,
  Tabs,
  Tab,
  Alert,
  AlertTitle,
  Button,
  LinearProgress,
  Tooltip,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  CloudQueue as CloudIcon,
  Timeline as TimelineIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  Settings as SettingsIcon,
  Dashboard as DashboardIcon,
  NetworkCheck as NetworkIcon,
  DataUsage as DataUsageIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  getExecutorMetrics,
  getCloudMetrics,
  getOtelStatus,
  getMetricsSummary,
} from '../services/api';
import type {
  ExecutorMetricsResponse,
  CloudMetricsResponse,
  OtelMetricsResponse,
  MetricsSummaryResponse,
} from '../types';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => (
  <div hidden={value !== index} style={{ paddingTop: 16 }}>
    {value === index && children}
  </div>
);

// Helper function to format bytes
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

// Helper function to format duration
const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
};

const Metrics: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState({
    executor: true,
    cloud: true,
    otel: true,
    summary: true,
  });
  const [error, setError] = useState({
    executor: null as string | null,
    cloud: null as string | null,
    otel: null as string | null,
    summary: null as string | null,
  });

  const [executorMetrics, setExecutorMetrics] = useState<ExecutorMetricsResponse | null>(null);
  const [cloudMetrics, setCloudMetrics] = useState<CloudMetricsResponse | null>(null);
  const [otelStatus, setOtelStatus] = useState<OtelMetricsResponse | null>(null);
  const [summaryMetrics, setSummaryMetrics] = useState<MetricsSummaryResponse | null>(null);

  const fetchExecutorMetrics = async () => {
    setLoading((prev) => ({ ...prev, executor: true }));
    setError((prev) => ({ ...prev, executor: null }));
    try {
      const data = await getExecutorMetrics();
      setExecutorMetrics(data);
    } catch (err) {
      setError((prev) => ({ ...prev, executor: 'Failed to fetch executor metrics' }));
      console.error('Failed to fetch executor metrics:', err);
    } finally {
      setLoading((prev) => ({ ...prev, executor: false }));
    }
  };

  const fetchCloudMetrics = async () => {
    setLoading((prev) => ({ ...prev, cloud: true }));
    setError((prev) => ({ ...prev, cloud: null }));
    try {
      const data = await getCloudMetrics();
      setCloudMetrics(data);
    } catch (err) {
      setError((prev) => ({ ...prev, cloud: 'Failed to fetch cloud metrics' }));
      console.error('Failed to fetch cloud metrics:', err);
    } finally {
      setLoading((prev) => ({ ...prev, cloud: false }));
    }
  };

  const fetchOtelStatus = async () => {
    setLoading((prev) => ({ ...prev, otel: true }));
    setError((prev) => ({ ...prev, otel: null }));
    try {
      const data = await getOtelStatus();
      setOtelStatus(data);
    } catch (err) {
      setError((prev) => ({ ...prev, otel: 'Failed to fetch OTEL status' }));
      console.error('Failed to fetch OTEL status:', err);
    } finally {
      setLoading((prev) => ({ ...prev, otel: false }));
    }
  };

  const fetchSummaryMetrics = async () => {
    setLoading((prev) => ({ ...prev, summary: true }));
    setError((prev) => ({ ...prev, summary: null }));
    try {
      const data = await getMetricsSummary();
      setSummaryMetrics(data);
    } catch (err) {
      setError((prev) => ({ ...prev, summary: 'Failed to fetch summary metrics' }));
      console.error('Failed to fetch summary metrics:', err);
    } finally {
      setLoading((prev) => ({ ...prev, summary: false }));
    }
  };

  useEffect(() => {
    fetchExecutorMetrics();
    fetchCloudMetrics();
    fetchOtelStatus();
    fetchSummaryMetrics();
  }, []);

  const handleRefresh = () => {
    switch (tabValue) {
      case 0:
        fetchExecutorMetrics();
        break;
      case 1:
        fetchCloudMetrics();
        break;
      case 2:
        fetchOtelStatus();
        break;
      case 3:
        fetchSummaryMetrics();
        break;
    }
  };

  const handleDownloadInitScript = () => {
    if (otelStatus?.init_script) {
      const blob = new Blob([otelStatus.init_script], { type: 'text/x-sh' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'otel-init-script.sh';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  // Executor Metrics Tab Content
  const renderExecutorMetrics = () => {
    if (loading.executor) {
      return (
        <Box sx={{ p: 2 }}>
          <Grid container spacing={3}>
            {[1, 2, 3, 4].map((i) => (
              <Grid item xs={12} sm={6} md={3} key={i}>
                <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 2 }} />
              </Grid>
            ))}
          </Grid>
          <Skeleton variant="rectangular" height={400} sx={{ mt: 3, borderRadius: 2 }} />
        </Box>
      );
    }

    if (error.executor) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            {error.executor}
          </Alert>
        </Box>
      );
    }

    if (!executorMetrics?.available) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="info">
            <AlertTitle>No Active Executors</AlertTitle>
            Executor metrics will be available when jobs are running on the cluster.
          </Alert>
        </Box>
      );
    }

    const { summary, executors } = executorMetrics;

    const memoryChartData = executors.map((e) => ({
      name: e.executor_id,
      used: e.memory_used_mb,
      max: e.memory_max_mb,
    }));

    const taskDistribution = [
      { name: 'Active', value: summary.total_active_tasks, color: '#2196f3' },
      { name: 'Completed', value: summary.total_completed_tasks, color: '#4caf50' },
      { name: 'Failed', value: summary.total_failed_tasks, color: '#f44336' },
    ].filter((d) => d.value > 0);

    return (
      <Box sx={{ p: 2 }}>
        {/* Summary Cards */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'primary.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Total Executors
                      </Typography>
                      <Typography variant="h4" fontWeight="bold">
                        {summary.total_executors}
                      </Typography>
                    </Box>
                    <SpeedIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'info.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Memory Usage
                      </Typography>
                      <Typography variant="h4" fontWeight="bold">
                        {summary.avg_memory_usage_percent.toFixed(1)}%
                      </Typography>
                      <Typography variant="caption">
                        {formatBytes(summary.total_memory_used_mb * 1024 * 1024)} /{' '}
                        {formatBytes(summary.total_memory_max_mb * 1024 * 1024)}
                      </Typography>
                    </Box>
                    <MemoryIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'warning.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        GC Time
                      </Typography>
                      <Typography variant="h4" fontWeight="bold">
                        {formatDuration(summary.total_gc_time_ms)}
                      </Typography>
                    </Box>
                    <TimelineIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'success.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Shuffle I/O
                      </Typography>
                      <Typography variant="h5" fontWeight="bold">
                        {formatBytes(summary.total_shuffle_read_bytes + summary.total_shuffle_write_bytes)}
                      </Typography>
                      <Typography variant="caption">
                        R: {formatBytes(summary.total_shuffle_read_bytes)} / W:{' '}
                        {formatBytes(summary.total_shuffle_write_bytes)}
                      </Typography>
                    </Box>
                    <StorageIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
        </Grid>

        {/* Charts */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
              <Typography variant="h6" gutterBottom>
                Memory Usage by Executor
              </Typography>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={memoryChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="name" stroke="#888" />
                  <YAxis stroke="#888" />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                    formatter={(value: number) => `${value} MB`}
                  />
                  <Bar dataKey="used" fill="#2196f3" name="Used MB" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="max" fill="#333" name="Max MB" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
              <Typography variant="h6" gutterBottom>
                Task Distribution
              </Typography>
              {taskDistribution.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={taskDistribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {taskDistribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      contentStyle={{
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #333',
                        borderRadius: 8,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Box
                  sx={{
                    height: 280,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Typography color="text.secondary">No tasks to display</Typography>
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>

        {/* Executor Table */}
        <Paper sx={{ p: 3, borderRadius: 3 }}>
          <Typography variant="h6" gutterBottom>
            Executor Details
          </Typography>
          <TableContainer sx={{ maxHeight: 400 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Executor ID</TableCell>
                  <TableCell>Host</TableCell>
                  <TableCell align="right">Memory Usage</TableCell>
                  <TableCell align="right">GC Time</TableCell>
                  <TableCell align="right">Shuffle Read</TableCell>
                  <TableCell align="right">Shuffle Write</TableCell>
                  <TableCell align="right">Tasks (A/C/F)</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {executors.map((executor) => (
                  <TableRow key={executor.executor_id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {executor.executor_id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {executor.host}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                        <LinearProgress
                          variant="determinate"
                          value={executor.memory_usage_percent}
                          sx={{ width: 60, height: 6, borderRadius: 3 }}
                          color={
                            executor.memory_usage_percent > 90
                              ? 'error'
                              : executor.memory_usage_percent > 70
                              ? 'warning'
                              : 'primary'
                          }
                        />
                        <Typography variant="body2">{executor.memory_usage_percent.toFixed(1)}%</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">{formatDuration(executor.gc_time_ms)}</TableCell>
                    <TableCell align="right">{formatBytes(executor.shuffle_read_bytes)}</TableCell>
                    <TableCell align="right">{formatBytes(executor.shuffle_write_bytes)}</TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'flex-end' }}>
                        <Chip label={executor.active_tasks} size="small" color="info" />
                        <Chip label={executor.completed_tasks} size="small" color="success" />
                        <Chip label={executor.failed_tasks} size="small" color="error" />
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      </Box>
    );
  };

  // Cloud Metrics Tab Content
  const renderCloudMetrics = () => {
    if (loading.cloud) {
      return (
        <Box sx={{ p: 2 }}>
          <Grid container spacing={3}>
            {[1, 2, 3, 4].map((i) => (
              <Grid item xs={12} sm={6} md={3} key={i}>
                <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 2 }} />
              </Grid>
            ))}
          </Grid>
        </Box>
      );
    }

    if (error.cloud) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            {error.cloud}
          </Alert>
        </Box>
      );
    }

    if (!cloudMetrics?.configured) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="info" sx={{ mb: 3 }}>
            <AlertTitle>Cloud Metrics Not Configured</AlertTitle>
            {cloudMetrics?.message || 'Cloud provider metrics integration is not set up.'}
          </Alert>

          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Setup Instructions
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              To enable cloud metrics, configure your cloud provider credentials and enable the metrics collection.
            </Typography>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              AWS CloudWatch
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Configure AWS credentials"
                  secondary="Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Enable CloudWatch metrics"
                  secondary="Ensure your EC2 instances have CloudWatch agent installed"
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Set CLOUD_METRICS_PROVIDER=aws"
                  secondary="Configure the environment variable in your backend"
                />
              </ListItem>
            </List>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              Azure Monitor
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Configure Azure credentials"
                  secondary="Set AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET"
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Set CLOUD_METRICS_PROVIDER=azure"
                  secondary="Configure the environment variable in your backend"
                />
              </ListItem>
            </List>

            <Divider sx={{ my: 2 }} />

            <Typography variant="subtitle2" gutterBottom>
              GCP Cloud Monitoring
            </Typography>
            <List dense>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Configure GCP credentials"
                  secondary="Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path"
                />
              </ListItem>
              <ListItem>
                <ListItemIcon>
                  <CheckIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary="Set CLOUD_METRICS_PROVIDER=gcp"
                  secondary="Configure the environment variable in your backend"
                />
              </ListItem>
            </List>
          </Paper>
        </Box>
      );
    }

    const { summary, metrics } = cloudMetrics;

    return (
      <Box sx={{ p: 2 }}>
        {/* Provider Badge */}
        <Box sx={{ mb: 3 }}>
          <Chip
            icon={<CloudIcon />}
            label={`Provider: ${cloudMetrics.provider?.toUpperCase() || 'Unknown'}`}
            color="primary"
            variant="outlined"
          />
        </Box>

        {/* Summary Cards */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'primary.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Avg CPU Usage
                      </Typography>
                      <Typography variant="h4" fontWeight="bold">
                        {summary?.avg_cpu_percent.toFixed(1)}%
                      </Typography>
                    </Box>
                    <SpeedIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'info.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Avg Memory Usage
                      </Typography>
                      <Typography variant="h4" fontWeight="bold">
                        {summary?.avg_memory_percent.toFixed(1)}%
                      </Typography>
                    </Box>
                    <MemoryIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'warning.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Disk I/O
                      </Typography>
                      <Typography variant="h5" fontWeight="bold">
                        {formatBytes(
                          (summary?.total_disk_read_bytes_per_sec || 0) +
                            (summary?.total_disk_write_bytes_per_sec || 0)
                        )}
                        /s
                      </Typography>
                    </Box>
                    <StorageIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <motion.div whileHover={{ scale: 1.02 }}>
              <Card sx={{ bgcolor: 'success.dark', color: 'white' }}>
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Box>
                      <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Network I/O
                      </Typography>
                      <Typography variant="h5" fontWeight="bold">
                        {formatBytes(
                          (summary?.total_network_in_bytes_per_sec || 0) +
                            (summary?.total_network_out_bytes_per_sec || 0)
                        )}
                        /s
                      </Typography>
                    </Box>
                    <NetworkIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                  </Box>
                </CardContent>
              </Card>
            </motion.div>
          </Grid>
        </Grid>

        {/* Instance Table */}
        <Paper sx={{ p: 3, borderRadius: 3 }}>
          <Typography variant="h6" gutterBottom>
            Instance Metrics
          </Typography>
          {metrics && metrics.length > 0 ? (
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Instance ID</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell align="right">CPU %</TableCell>
                    <TableCell align="right">Memory %</TableCell>
                    <TableCell align="right">Disk Read</TableCell>
                    <TableCell align="right">Disk Write</TableCell>
                    <TableCell align="right">Net In</TableCell>
                    <TableCell align="right">Net Out</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {metrics.map((instance) => (
                    <TableRow key={instance.instance_id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {instance.instance_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={instance.instance_type} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                          <LinearProgress
                            variant="determinate"
                            value={instance.cpu_usage_percent}
                            sx={{ width: 60, height: 6, borderRadius: 3 }}
                            color={
                              instance.cpu_usage_percent > 90
                                ? 'error'
                                : instance.cpu_usage_percent > 70
                                ? 'warning'
                                : 'primary'
                            }
                          />
                          <Typography variant="body2">{instance.cpu_usage_percent.toFixed(1)}%</Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                          <LinearProgress
                            variant="determinate"
                            value={instance.memory_usage_percent}
                            sx={{ width: 60, height: 6, borderRadius: 3 }}
                            color={
                              instance.memory_usage_percent > 90
                                ? 'error'
                                : instance.memory_usage_percent > 70
                                ? 'warning'
                                : 'info'
                            }
                          />
                          <Typography variant="body2">{instance.memory_usage_percent.toFixed(1)}%</Typography>
                        </Box>
                      </TableCell>
                      <TableCell align="right">{formatBytes(instance.disk_read_bytes_per_sec)}/s</TableCell>
                      <TableCell align="right">{formatBytes(instance.disk_write_bytes_per_sec)}/s</TableCell>
                      <TableCell align="right">{formatBytes(instance.network_in_bytes_per_sec)}/s</TableCell>
                      <TableCell align="right">{formatBytes(instance.network_out_bytes_per_sec)}/s</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Alert severity="info">No instance metrics available.</Alert>
          )}
        </Paper>
      </Box>
    );
  };

  // OTEL Metrics Tab Content
  const renderOtelMetrics = () => {
    if (loading.otel) {
      return (
        <Box sx={{ p: 2 }}>
          <Skeleton variant="rectangular" height={200} sx={{ borderRadius: 2 }} />
        </Box>
      );
    }

    if (error.otel) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            {error.otel}
          </Alert>
        </Box>
      );
    }

    if (!otelStatus?.configured) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="info" sx={{ mb: 3 }}>
            <AlertTitle>OpenTelemetry Not Configured</AlertTitle>
            {otelStatus?.message || 'OpenTelemetry integration is not set up for this workspace.'}
          </Alert>

          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Setup OpenTelemetry for Databricks
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              OpenTelemetry provides comprehensive observability for your Spark jobs including distributed tracing,
              metrics, and logs.
            </Typography>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SettingsIcon fontSize="small" /> Step 1: Download Init Script
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Download the cluster init script that configures OpenTelemetry on your Databricks clusters.
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownloadInitScript}
                  disabled={!otelStatus?.init_script}
                >
                  Download Init Script
                </Button>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CloudIcon fontSize="small" /> Step 2: Upload to DBFS
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Upload the init script to your Databricks File System (DBFS):
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    bgcolor: 'background.default',
                    p: 2,
                    borderRadius: 1,
                    overflow: 'auto',
                    fontSize: 12,
                    mt: 1,
                  }}
                >
                  dbfs:/databricks/scripts/otel-init.sh
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SpeedIcon fontSize="small" /> Step 3: Configure Cluster
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Add the init script to your cluster configuration under Advanced Options &gt; Init Scripts.
                </Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DashboardIcon fontSize="small" /> Step 4: Set Environment Variables
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure the following environment variables:
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    bgcolor: 'background.default',
                    p: 2,
                    borderRadius: 1,
                    overflow: 'auto',
                    fontSize: 12,
                    mt: 1,
                  }}
                >
                  {`OTEL_EXPORTER_OTLP_ENDPOINT=${otelStatus?.endpoint || 'https://your-collector:4317'}
OTEL_SERVICE_NAME=databricks-spark
OTEL_RESOURCE_ATTRIBUTES=service.namespace=databricks`}
                </Box>
              </Grid>
            </Grid>

            <Divider sx={{ my: 3 }} />

            <Typography variant="subtitle2" gutterBottom>
              Benefits of OpenTelemetry Integration
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardContent>
                    <TimelineIcon color="primary" sx={{ mb: 1 }} />
                    <Typography variant="subtitle2">Distributed Tracing</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Track requests across Spark stages and tasks
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardContent>
                    <DataUsageIcon color="primary" sx={{ mb: 1 }} />
                    <Typography variant="subtitle2">Rich Metrics</Typography>
                    <Typography variant="body2" color="text.secondary">
                      CPU, memory, I/O metrics at granular level
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardContent>
                    <StorageIcon color="primary" sx={{ mb: 1 }} />
                    <Typography variant="subtitle2">Log Correlation</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Correlate logs with traces and metrics
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Card variant="outlined" sx={{ height: '100%' }}>
                  <CardContent>
                    <DashboardIcon color="primary" sx={{ mb: 1 }} />
                    <Typography variant="subtitle2">Dashboards</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Pre-built Grafana/Datadog dashboards
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Paper>
        </Box>
      );
    }

    // OTEL is configured - show metrics and dashboards
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="success" sx={{ mb: 3 }}>
          <AlertTitle>OpenTelemetry Configured</AlertTitle>
          Endpoint: {otelStatus.endpoint}
        </Alert>

        {/* Dashboard Links */}
        {otelStatus.dashboards && otelStatus.dashboards.length > 0 && (
          <Paper sx={{ p: 3, borderRadius: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Available Dashboards
            </Typography>
            <Grid container spacing={2}>
              {otelStatus.dashboards.map((dashboard, index) => (
                <Grid item xs={12} sm={6} md={4} key={index}>
                  <Card variant="outlined">
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <DashboardIcon color="primary" />
                        <Typography variant="subtitle2">{dashboard.name}</Typography>
                      </Box>
                      <Button
                        size="small"
                        href={dashboard.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ mt: 1 }}
                      >
                        Open Dashboard
                      </Button>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        )}

        {/* OTEL Metrics Table */}
        {otelStatus.metrics && otelStatus.metrics.length > 0 && (
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Recent Metrics
            </Typography>
            <TableContainer sx={{ maxHeight: 400 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Metric Name</TableCell>
                    <TableCell align="right">Value</TableCell>
                    <TableCell>Unit</TableCell>
                    <TableCell>Labels</TableCell>
                    <TableCell>Timestamp</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {otelStatus.metrics.map((metric, index) => (
                    <TableRow key={index} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {metric.name}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2">{metric.value.toFixed(2)}</Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={metric.unit} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                          {Object.entries(metric.labels).slice(0, 3).map(([key, value]) => (
                            <Tooltip key={key} title={`${key}: ${value}`}>
                              <Chip label={`${key}=${value}`} size="small" sx={{ fontSize: 10 }} />
                            </Tooltip>
                          ))}
                          {Object.keys(metric.labels).length > 3 && (
                            <Chip label={`+${Object.keys(metric.labels).length - 3}`} size="small" />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {new Date(metric.timestamp).toLocaleString()}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        )}
      </Box>
    );
  };

  // Summary Tab Content
  const renderSummary = () => {
    if (loading.summary) {
      return (
        <Box sx={{ p: 2 }}>
          <Grid container spacing={3}>
            {[1, 2, 3, 4].map((i) => (
              <Grid item xs={12} sm={6} md={3} key={i}>
                <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 2 }} />
              </Grid>
            ))}
          </Grid>
        </Box>
      );
    }

    if (error.summary) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">
            <AlertTitle>Error</AlertTitle>
            {error.summary}
          </Alert>
        </Box>
      );
    }

    if (!summaryMetrics) {
      return (
        <Box sx={{ p: 2 }}>
          <Alert severity="info">No metrics available.</Alert>
        </Box>
      );
    }

    const { metrics, source_label, available_tiers } = summaryMetrics;

    return (
      <Box sx={{ p: 2 }}>
        {/* Source Indicator */}
        <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            icon={<InfoIcon />}
            label={`Data Source: ${source_label}`}
            color="primary"
            variant="outlined"
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Executor Metrics (Tier 1)">
              <Chip
                icon={available_tiers.executor ? <CheckIcon /> : <ErrorIcon />}
                label="Executor"
                size="small"
                color={available_tiers.executor ? 'success' : 'default'}
                variant="outlined"
              />
            </Tooltip>
            <Tooltip title="Cloud Metrics (Tier 2)">
              <Chip
                icon={available_tiers.cloud ? <CheckIcon /> : <ErrorIcon />}
                label="Cloud"
                size="small"
                color={available_tiers.cloud ? 'success' : 'default'}
                variant="outlined"
              />
            </Tooltip>
            <Tooltip title="OTEL Metrics (Tier 3)">
              <Chip
                icon={available_tiers.otel ? <CheckIcon /> : <ErrorIcon />}
                label="OTEL"
                size="small"
                color={available_tiers.otel ? 'success' : 'default'}
                variant="outlined"
              />
            </Tooltip>
          </Box>
        </Box>

        {/* Summary Cards */}
        <Grid container spacing={3}>
          {metrics.cpu_usage_percent !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'primary.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          CPU Usage
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {metrics.cpu_usage_percent.toFixed(1)}%
                        </Typography>
                      </Box>
                      <SpeedIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.memory_usage_percent !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'info.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Memory Usage
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {metrics.memory_usage_percent.toFixed(1)}%
                        </Typography>
                      </Box>
                      <MemoryIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.gc_time_ms !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'warning.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          GC Time
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {formatDuration(metrics.gc_time_ms)}
                        </Typography>
                      </Box>
                      <TimelineIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.shuffle_io_bytes !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'success.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Shuffle I/O
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {formatBytes(metrics.shuffle_io_bytes)}
                        </Typography>
                      </Box>
                      <StorageIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.disk_io_bytes_per_sec !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'secondary.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Disk I/O
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {formatBytes(metrics.disk_io_bytes_per_sec)}/s
                        </Typography>
                      </Box>
                      <StorageIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.network_io_bytes_per_sec !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'error.dark', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Network I/O
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {formatBytes(metrics.network_io_bytes_per_sec)}/s
                        </Typography>
                      </Box>
                      <NetworkIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {metrics.active_tasks !== undefined && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'primary.main', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Active Tasks
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {metrics.active_tasks}
                        </Typography>
                      </Box>
                      <TimelineIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}

          {(metrics.completed_tasks !== undefined || metrics.failed_tasks !== undefined) && (
            <Grid item xs={12} sm={6} md={3}>
              <motion.div whileHover={{ scale: 1.02 }}>
                <Card sx={{ bgcolor: 'grey.800', color: 'white' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="body2" sx={{ opacity: 0.8 }}>
                          Tasks (C/F)
                        </Typography>
                        <Typography variant="h4" fontWeight="bold">
                          {metrics.completed_tasks || 0}/{metrics.failed_tasks || 0}
                        </Typography>
                      </Box>
                      <DataUsageIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          )}
        </Grid>

        {/* Tier Explanation */}
        <Paper sx={{ p: 3, mt: 3, borderRadius: 3 }}>
          <Typography variant="h6" gutterBottom>
            Metrics Tier Architecture
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{
                  height: '100%',
                  borderColor: available_tiers.executor ? 'success.main' : 'grey.700',
                }}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip label="Tier 1" size="small" color="primary" />
                    {available_tiers.executor && <CheckIcon color="success" fontSize="small" />}
                  </Box>
                  <Typography variant="subtitle2">Executor Metrics</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Always available from Spark executors. Provides memory, GC, shuffle, and task metrics.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{
                  height: '100%',
                  borderColor: available_tiers.cloud ? 'success.main' : 'grey.700',
                }}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip label="Tier 2" size="small" color="info" />
                    {available_tiers.cloud && <CheckIcon color="success" fontSize="small" />}
                  </Box>
                  <Typography variant="subtitle2">Cloud Metrics</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Requires cloud provider configuration. Provides CPU, memory, disk, and network I/O from VMs.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={4}>
              <Card
                variant="outlined"
                sx={{
                  height: '100%',
                  borderColor: available_tiers.otel ? 'success.main' : 'grey.700',
                }}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip label="Tier 3" size="small" color="secondary" />
                    {available_tiers.otel && <CheckIcon color="success" fontSize="small" />}
                  </Box>
                  <Typography variant="subtitle2">OTEL Metrics</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Requires OpenTelemetry setup. Provides comprehensive observability with tracing and custom metrics.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Paper>
      </Box>
    );
  };

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Metrics
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Monitor cluster and job metrics across multiple sources (3-tier architecture)
          </Typography>
        </Box>
        <Tooltip title="Refresh current tab">
          <IconButton onClick={handleRefresh} color="primary">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Tabs */}
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tabValue}
          onChange={(_, newValue) => setTabValue(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
          variant="scrollable"
          scrollButtons="auto"
        >
          <Tab
            label="Executor Metrics"
            icon={<SpeedIcon />}
            iconPosition="start"
            sx={{ minHeight: 64 }}
          />
          <Tab
            label="Cloud Metrics"
            icon={<CloudIcon />}
            iconPosition="start"
            sx={{ minHeight: 64 }}
          />
          <Tab
            label="OTEL Metrics"
            icon={<TimelineIcon />}
            iconPosition="start"
            sx={{ minHeight: 64 }}
          />
          <Tab
            label="Summary"
            icon={<DashboardIcon />}
            iconPosition="start"
            sx={{ minHeight: 64 }}
          />
        </Tabs>

        {/* Tab Panels */}
        <TabPanel value={tabValue} index={0}>
          {renderExecutorMetrics()}
        </TabPanel>
        <TabPanel value={tabValue} index={1}>
          {renderCloudMetrics()}
        </TabPanel>
        <TabPanel value={tabValue} index={2}>
          {renderOtelMetrics()}
        </TabPanel>
        <TabPanel value={tabValue} index={3}>
          {renderSummary()}
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default Metrics;
