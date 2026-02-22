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
  LinearProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
  Schedule as ScheduleIcon,
  Refresh as RetryIcon,
  TrendingUp as AnomalyIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  getFailedJobs,
  getProlongedJobs,
  getAnomalies,
  getRetryStats,
} from '../services/api';
import type { FailedJob, ProlongedJob, Anomaly, RetryStats } from '../types';

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

const statusColors: Record<string, string> = {
  NORMAL: '#4caf50',
  WARNING: '#ff9800',
  CRITICAL: '#f44336',
  ANOMALY: '#9c27b0',
};

const Health: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failedJobs, setFailedJobs] = useState<FailedJob[]>([]);
  const [prolongedJobs, setProlongedJobs] = useState<ProlongedJob[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [retryStats, setRetryStats] = useState<RetryStats[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [failed, prolonged, anomalyData, retries] = await Promise.all([
          getFailedJobs(7),
          getProlongedJobs(60, 180),
          getAnomalies(7, 2.0, 3.0),
          getRetryStats(7),
        ]);
        setFailedJobs(failed);
        setProlongedJobs(prolonged);
        setAnomalies(anomalyData);
        setRetryStats(retries);
      } catch (error) {
        console.error('Failed to fetch health data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const criticalCount = anomalies.filter((a) => a.severity === 'CRITICAL').length;
  const warningCount = anomalies.filter((a) => a.severity === 'WARNING').length;
  const prolongedCritical = prolongedJobs.filter(
    (j) => j.duration_status === 'CRITICAL'
  ).length;

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Health & Anomalies
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor job health, detect anomalies, and track prolonged jobs
        </Typography>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <motion.div whileHover={{ scale: 1.02 }}>
            <Card sx={{ bgcolor: 'error.dark', color: 'white' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Box>
                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                      Failed Jobs
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : failedJobs.length}
                    </Typography>
                  </Box>
                  <ErrorIcon sx={{ fontSize: 40, opacity: 0.8 }} />
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
                      Prolonged Jobs
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : prolongedJobs.length}
                    </Typography>
                    <Typography variant="caption">
                      {prolongedCritical} critical
                    </Typography>
                  </Box>
                  <ScheduleIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <motion.div whileHover={{ scale: 1.02 }}>
            <Card sx={{ bgcolor: 'secondary.dark', color: 'white' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Box>
                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                      Anomalies
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : anomalies.length}
                    </Typography>
                    <Typography variant="caption">
                      {criticalCount} critical, {warningCount} warning
                    </Typography>
                  </Box>
                  <AnomalyIcon sx={{ fontSize: 40, opacity: 0.8 }} />
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
                      Jobs with Retries
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : retryStats.length}
                    </Typography>
                  </Box>
                  <RetryIcon sx={{ fontSize: 40, opacity: 0.8 }} />
                </Box>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Paper sx={{ borderRadius: 2 }}>
        <Tabs
          value={tabValue}
          onChange={(_, newValue) => setTabValue(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Failed Jobs" icon={<ErrorIcon />} iconPosition="start" />
          <Tab label="Prolonged Jobs" icon={<ScheduleIcon />} iconPosition="start" />
          <Tab label="Anomalies" icon={<AnomalyIcon />} iconPosition="start" />
          <Tab label="Retry Stats" icon={<RetryIcon />} iconPosition="start" />
        </Tabs>

        {/* Failed Jobs Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ p: 2 }}>
            {loading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : failedJobs.length === 0 ? (
              <Alert severity="success" icon={<SuccessIcon />}>
                No failed jobs in the last 7 days!
              </Alert>
            ) : (
              <Grid container spacing={3}>
                <Grid item xs={12} md={8}>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Job Name</TableCell>
                          <TableCell align="right">Total Runs</TableCell>
                          <TableCell align="right">Failed</TableCell>
                          <TableCell align="right">Success Rate</TableCell>
                          <TableCell>Run As</TableCell>
                          <TableCell>Last Run</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {failedJobs.map((job) => (
                          <TableRow key={job.job_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight={500}>
                                {job.job_name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {job.job_id}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">{job.total_runs}</TableCell>
                            <TableCell align="right">
                              <Chip
                                label={job.failed_runs}
                                size="small"
                                color="error"
                              />
                            </TableCell>
                            <TableCell align="right">
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <LinearProgress
                                  variant="determinate"
                                  value={job.success_rate}
                                  sx={{ width: 60, height: 6, borderRadius: 3 }}
                                  color={job.success_rate < 50 ? 'error' : 'warning'}
                                />
                                <Typography variant="body2">
                                  {Number(job.success_rate || 0).toFixed(1)}%
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" noWrap sx={{ maxWidth: 120 }}>
                                {job.run_as}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2">
                                {job.last_run ? new Date(job.last_run).toLocaleString() : '-'}
                              </Typography>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" gutterBottom>
                    Failure Distribution
                  </Typography>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={failedJobs.slice(0, 10)}
                      layout="vertical"
                      margin={{ left: 100 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis type="number" stroke="#888" />
                      <YAxis
                        type="category"
                        dataKey="job_name"
                        stroke="#888"
                        tick={{ fontSize: 10 }}
                        width={90}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: '#1a1a2e',
                          border: '1px solid #333',
                          borderRadius: 8,
                        }}
                      />
                      <Bar dataKey="failed_runs" fill="#f44336" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Grid>
              </Grid>
            )}
          </Box>
        </TabPanel>

        {/* Prolonged Jobs Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ p: 2 }}>
            {loading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : prolongedJobs.length === 0 ? (
              <Alert severity="success" icon={<SuccessIcon />}>
                No prolonged jobs currently running!
              </Alert>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Job Name</TableCell>
                      <TableCell>Run ID</TableCell>
                      <TableCell align="right">Running Time</TableCell>
                      <TableCell align="right">Avg Duration</TableCell>
                      <TableCell>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {prolongedJobs.map((job) => (
                      <TableRow
                        key={`${job.job_id}-${job.run_id}`}
                        hover
                        sx={{
                          bgcolor:
                            job.duration_status === 'CRITICAL'
                              ? 'rgba(244, 67, 54, 0.1)'
                              : job.duration_status === 'WARNING'
                              ? 'rgba(255, 152, 0, 0.1)'
                              : 'transparent',
                        }}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {job.job_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {job.job_id}
                          </Typography>
                        </TableCell>
                        <TableCell>{job.run_id}</TableCell>
                        <TableCell align="right">
                          <Typography
                            variant="body2"
                            fontWeight={600}
                            color={
                              job.duration_status === 'CRITICAL'
                                ? 'error.main'
                                : job.duration_status === 'WARNING'
                                ? 'warning.main'
                                : 'text.primary'
                            }
                          >
                            {Number(job.running_minutes || 0).toFixed(0)} min
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          {Number(job.avg_duration_minutes || 0).toFixed(0)} min
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={job.duration_status}
                            size="small"
                            sx={{
                              bgcolor: `${statusColors[job.duration_status]}20`,
                              color: statusColors[job.duration_status],
                              fontWeight: 600,
                            }}
                            icon={
                              job.duration_status === 'CRITICAL' ? (
                                <ErrorIcon sx={{ color: 'inherit !important' }} />
                              ) : job.duration_status === 'WARNING' ? (
                                <WarningIcon sx={{ color: 'inherit !important' }} />
                              ) : undefined
                            }
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </TabPanel>

        {/* Anomalies Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ p: 2 }}>
            {loading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : anomalies.length === 0 ? (
              <Alert severity="success" icon={<SuccessIcon />}>
                No anomalies detected in the last 7 days!
              </Alert>
            ) : (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Job Name</TableCell>
                      <TableCell>Metric</TableCell>
                      <TableCell align="right">Actual</TableCell>
                      <TableCell align="right">Expected</TableCell>
                      <TableCell align="right">Z-Score</TableCell>
                      <TableCell>Severity</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {anomalies.map((anomaly, idx) => (
                      <TableRow
                        key={`${anomaly.job_id}-${anomaly.run_id}-${idx}`}
                        hover
                        sx={{
                          bgcolor:
                            anomaly.severity === 'CRITICAL'
                              ? 'rgba(244, 67, 54, 0.1)'
                              : 'rgba(255, 152, 0, 0.1)',
                        }}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {anomaly.job_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Run: {anomaly.run_id}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={anomaly.metric_name} size="small" variant="outlined" />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" fontWeight={600}>
                            {Number(anomaly.metric_value || 0).toFixed(2)}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          {Number(anomaly.expected_value || 0).toFixed(2)}
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="Standard deviations from mean">
                            <Typography
                              variant="body2"
                              color={
                                Math.abs(Number(anomaly.z_score || 0)) > 3
                                  ? 'error.main'
                                  : 'warning.main'
                              }
                            >
                              {Number(anomaly.z_score || 0).toFixed(2)}σ
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={anomaly.severity}
                            size="small"
                            color={anomaly.severity === 'CRITICAL' ? 'error' : 'warning'}
                            icon={
                              anomaly.severity === 'CRITICAL' ? (
                                <ErrorIcon />
                              ) : (
                                <WarningIcon />
                              )
                            }
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Box>
        </TabPanel>

        {/* Retry Stats Tab */}
        <TabPanel value={tabValue} index={3}>
          <Box sx={{ p: 2 }}>
            {loading ? (
              <Skeleton variant="rectangular" height={300} />
            ) : retryStats.length === 0 ? (
              <Alert severity="info">No retry statistics available.</Alert>
            ) : (
              <Grid container spacing={3}>
                <Grid item xs={12} md={8}>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Job Name</TableCell>
                          <TableCell align="right">Runs with Retries</TableCell>
                          <TableCell align="right">Total Retries</TableCell>
                          <TableCell align="right">Retry Success Rate</TableCell>
                          <TableCell align="right">Avg Attempts</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {retryStats.map((stat) => (
                          <TableRow key={stat.job_id} hover>
                            <TableCell>
                              <Typography variant="body2" fontWeight={500}>
                                {stat.job_name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {stat.job_id}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">{stat.runs_with_retries}</TableCell>
                            <TableCell align="right">
                              <Chip
                                label={stat.total_retries}
                                size="small"
                                color={stat.total_retries > 10 ? 'warning' : 'default'}
                              />
                            </TableCell>
                            <TableCell align="right">
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <LinearProgress
                                  variant="determinate"
                                  value={stat.retry_success_rate}
                                  sx={{ width: 60, height: 6, borderRadius: 3 }}
                                  color={
                                    stat.retry_success_rate > 80
                                      ? 'success'
                                      : stat.retry_success_rate > 50
                                      ? 'warning'
                                      : 'error'
                                  }
                                />
                                <Typography variant="body2">
                                  {Number(stat.retry_success_rate || 0).toFixed(1)}%
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              {Number(stat.avg_attempts_per_run || 0).toFixed(1)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Grid>
                <Grid item xs={12} md={4}>
                  <Typography variant="subtitle2" gutterBottom>
                    Retry Count by Job
                  </Typography>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={retryStats.slice(0, 10)}
                      layout="vertical"
                      margin={{ left: 100 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis type="number" stroke="#888" />
                      <YAxis
                        type="category"
                        dataKey="job_name"
                        stroke="#888"
                        tick={{ fontSize: 10 }}
                        width={90}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: '#1a1a2e',
                          border: '1px solid #333',
                          borderRadius: 8,
                        }}
                      />
                      <Bar dataKey="total_retries" fill="#2196f3" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Grid>
              </Grid>
            )}
          </Box>
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default Health;
