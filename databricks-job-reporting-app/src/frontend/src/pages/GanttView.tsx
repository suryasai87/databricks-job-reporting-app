import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Skeleton,
  Chip,
  Alert,
  Tooltip,
  IconButton,
  Grid,
} from '@mui/material';
import {
  ZoomIn as ZoomInIcon,
  ZoomOut as ZoomOutIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { getJobRuns, getOverlaps, getConcurrentJobsOverTime } from '../services/api';
import type { JobRun, Overlap } from '../types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';

const statusColors: Record<string, string> = {
  SUCCESS: '#4caf50',
  FAILED: '#f44336',
  RUNNING: '#ff9800',
  CANCELLED: '#9e9e9e',
  PENDING: '#2196f3',
};

const GanttView: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [overlaps, setOverlaps] = useState<Overlap[]>([]);
  const [concurrent, setConcurrent] = useState<any[]>([]);
  const [hours, setHours] = useState(24);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [jobsData, overlapsData, concurrentData] = await Promise.all([
          getJobRuns(1, 100),
          getOverlaps(1),
          getConcurrentJobsOverTime(hours),
        ]);
        setJobs(jobsData);
        setOverlaps(overlapsData);
        setConcurrent(concurrentData);
      } catch (error) {
        console.error('Failed to fetch Gantt data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [hours]);

  const timeRange = useMemo(() => {
    if (jobs.length === 0) return { start: new Date(), end: new Date() };
    const times = jobs
      .filter((j) => j.start_time)
      .flatMap((j) => [
        new Date(j.start_time!).getTime(),
        j.end_time ? new Date(j.end_time).getTime() : Date.now(),
      ]);
    if (times.length === 0) return { start: new Date(), end: new Date() };
    return {
      start: new Date(Math.min(...times)),
      end: new Date(Math.max(...times)),
    };
  }, [jobs]);

  const rangeMs = timeRange.end.getTime() - timeRange.start.getTime();

  const getBarPosition = (startTime: string, endTime: string | null) => {
    const start = new Date(startTime).getTime();
    const end = endTime ? new Date(endTime).getTime() : Date.now();
    const left = ((start - timeRange.start.getTime()) / rangeMs) * 100;
    const width = ((end - start) / rangeMs) * 100;
    return { left: `${left}%`, width: `${Math.max(width, 0.5)}%` };
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const hasOverlap = (jobId: string, runId: string) => {
    return overlaps.some(
      (o) =>
        (o.job_a === jobId && o.run_a === runId) ||
        (o.job_b === jobId && o.run_b === runId)
    );
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Gantt View
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Visualize job execution timeline and detect overlaps
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={hours}
              label="Time Range"
              onChange={(e) => setHours(Number(e.target.value))}
            >
              <MenuItem value={6}>Last 6 Hours</MenuItem>
              <MenuItem value={12}>Last 12 Hours</MenuItem>
              <MenuItem value={24}>Last 24 Hours</MenuItem>
              <MenuItem value={48}>Last 48 Hours</MenuItem>
            </Select>
          </FormControl>
          <IconButton onClick={() => setZoom((z) => Math.min(z + 0.25, 2))}>
            <ZoomInIcon />
          </IconButton>
          <IconButton onClick={() => setZoom((z) => Math.max(z - 0.25, 0.5))}>
            <ZoomOutIcon />
          </IconButton>
          <Chip label={`${overlaps.length} overlaps`} color={overlaps.length > 0 ? 'warning' : 'success'} />
        </Box>
      </Box>

      {overlaps.length > 0 && (
        <Alert severity="warning" sx={{ mb: 3 }} icon={<WarningIcon />}>
          {overlaps.length} job overlap(s) detected. Consider staggering job schedules to reduce resource contention.
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Gantt Chart */}
        <Grid item xs={12} lg={8}>
          <Paper sx={{ p: 3, borderRadius: 3, overflow: 'hidden' }}>
            <Typography variant="h6" gutterBottom>
              Job Execution Timeline
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={400} />
            ) : jobs.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Typography color="text.secondary">No jobs found in the selected time range</Typography>
              </Box>
            ) : (
              <Box sx={{ overflowX: 'auto' }}>
                {/* Time axis */}
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    borderBottom: 1,
                    borderColor: 'divider',
                    pb: 1,
                    mb: 2,
                    minWidth: 800 * zoom,
                  }}
                >
                  {Array.from({ length: 5 }).map((_, i) => {
                    const time = new Date(
                      timeRange.start.getTime() + (rangeMs / 4) * i
                    );
                    return (
                      <Typography key={i} variant="caption" color="text.secondary">
                        {formatTime(time)}
                      </Typography>
                    );
                  })}
                </Box>

                {/* Gantt bars */}
                <Box sx={{ minWidth: 800 * zoom }}>
                  {jobs.filter((j) => j.start_time).slice(0, 20).map((job) => {
                    const pos = getBarPosition(job.start_time!, job.end_time);
                    const isOverlapping = hasOverlap(job.job_id || '', job.run_id || '');
                    return (
                      <Box
                        key={`${job.job_id || 'unknown'}-${job.run_id || 'unknown'}`}
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          mb: 1,
                          '&:hover': { bgcolor: 'action.hover' },
                        }}
                      >
                        <Box sx={{ width: 180, flexShrink: 0, pr: 2 }}>
                          <Tooltip title={`Job: ${job.job_id || '-'}, Run: ${job.run_id || '-'}`}>
                            <Typography
                              variant="body2"
                              noWrap
                              sx={{
                                fontWeight: isOverlapping ? 600 : 400,
                                color: isOverlapping ? 'warning.main' : 'text.primary',
                              }}
                            >
                              {job.job_name || 'Unknown'}
                            </Typography>
                          </Tooltip>
                        </Box>
                        <Box sx={{ flex: 1, position: 'relative', height: 24 }}>
                          <Tooltip
                            title={
                              <Box>
                                <Typography variant="body2">
                                  Start: {job.start_time ? new Date(job.start_time).toLocaleString() : 'N/A'}
                                </Typography>
                                <Typography variant="body2">
                                  End: {job.end_time ? new Date(job.end_time).toLocaleString() : 'Running'}
                                </Typography>
                                <Typography variant="body2">
                                  Duration: {job.duration_seconds ? `${Math.round(job.duration_seconds / 60)} min` : 'N/A'}
                                </Typography>
                                <Typography variant="body2">
                                  Status: {job.result_state || 'RUNNING'}
                                </Typography>
                                {isOverlapping && (
                                  <Typography variant="body2" color="warning.main">
                                    ⚠️ Overlaps with other jobs
                                  </Typography>
                                )}
                              </Box>
                            }
                          >
                            <Box
                              sx={{
                                position: 'absolute',
                                top: 2,
                                height: 20,
                                borderRadius: 1,
                                bgcolor: statusColors[job.result_state || 'RUNNING'],
                                opacity: 0.9,
                                cursor: 'pointer',
                                transition: 'opacity 0.2s',
                                border: isOverlapping ? '2px solid #ff9800' : 'none',
                                '&:hover': { opacity: 1 },
                                ...pos,
                              }}
                            />
                          </Tooltip>
                        </Box>
                      </Box>
                    );
                  })}
                </Box>

                {/* Legend */}
                <Box sx={{ display: 'flex', gap: 2, mt: 3, flexWrap: 'wrap' }}>
                  {Object.entries(statusColors).map(([status, color]) => (
                    <Box key={status} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: color }} />
                      <Typography variant="caption">{status}</Typography>
                    </Box>
                  ))}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        borderRadius: 0.5,
                        bgcolor: 'grey.500',
                        border: '2px solid #ff9800',
                      }}
                    />
                    <Typography variant="caption">Overlapping</Typography>
                  </Box>
                </Box>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Concurrent Jobs Chart */}
        <Grid item xs={12} lg={4}>
          <Paper sx={{ p: 3, borderRadius: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Concurrent Jobs Over Time
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={350} />
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={concurrent}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="time" stroke="#888" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#888" />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                  />
                  <Line
                    type="stepAfter"
                    dataKey="concurrent_jobs"
                    stroke="#FF3621"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>

        {/* Overlaps Table */}
        {overlaps.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3, borderRadius: 3 }}>
              <Typography variant="h6" gutterBottom>
                Detected Overlaps
              </Typography>
              <Box sx={{ overflowX: 'auto' }}>
                <Box
                  component="table"
                  sx={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    '& th, & td': {
                      p: 1.5,
                      textAlign: 'left',
                      borderBottom: 1,
                      borderColor: 'divider',
                    },
                    '& th': { fontWeight: 600 },
                  }}
                >
                  <thead>
                    <tr>
                      <th>Job A</th>
                      <th>Run A</th>
                      <th>Job B</th>
                      <th>Run B</th>
                      <th>Overlap Duration</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overlaps.slice(0, 10).map((overlap, idx) => (
                      <tr key={idx}>
                        <td>
                          <Typography variant="body2">{overlap.job_a}</Typography>
                        </td>
                        <td>
                          <Chip label={overlap.run_a} size="small" variant="outlined" />
                        </td>
                        <td>
                          <Typography variant="body2">{overlap.job_b}</Typography>
                        </td>
                        <td>
                          <Chip label={overlap.run_b} size="small" variant="outlined" />
                        </td>
                        <td>
                          <Chip
                            label={`${Number(overlap.overlap_minutes || 0).toFixed(1)} min`}
                            size="small"
                            color="warning"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Box>
              </Box>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};

export default GanttView;
