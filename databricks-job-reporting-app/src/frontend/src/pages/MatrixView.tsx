import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Skeleton,
  Tooltip,
  TextField,
  InputAdornment,
  Chip,
} from '@mui/material';
import {
  Search as SearchIcon,
  GridView as GridViewIcon,
} from '@mui/icons-material';
import { getJobsMatrix } from '../services/api';
import type { MatrixData, MatrixRunCell } from '../types';

// Status colors matching the requirements
const statusColors: Record<string, string> = {
  SUCCESS: '#4caf50',    // Green
  FAILED: '#f44336',     // Red
  RUNNING: '#ff9800',    // Yellow/Orange
  PENDING: '#9e9e9e',    // Grey
  CANCELLED: '#9e9e9e',  // Grey
  UNKNOWN: '#bdbdbd',    // Light grey for null/unknown
};

const formatDuration = (seconds: number | null): string => {
  if (seconds === null || seconds === undefined) return 'N/A';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
};

const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return 'N/A';
  }
};

interface RunCellProps {
  run: MatrixRunCell | null;
  onClick: () => void;
}

const RunCell: React.FC<RunCellProps> = ({ run, onClick }) => {
  if (!run) {
    return (
      <Box
        sx={{
          width: 32,
          height: 32,
          borderRadius: 1,
          bgcolor: 'action.disabledBackground',
          cursor: 'default',
        }}
      />
    );
  }

  const status = run.result_state || 'UNKNOWN';
  const color = statusColors[status] || statusColors.UNKNOWN;

  return (
    <Tooltip
      title={
        <Box sx={{ p: 0.5 }}>
          <Typography variant="body2" fontWeight="bold">
            Run ID: {run.run_id || 'N/A'}
          </Typography>
          <Typography variant="body2">
            Status: <Chip label={status} size="small" sx={{ bgcolor: color, color: 'white', height: 20 }} />
          </Typography>
          <Typography variant="body2">
            Duration: {formatDuration(run.duration_seconds)}
          </Typography>
          <Typography variant="body2">
            Start: {formatTimestamp(run.start_time)}
          </Typography>
          <Typography variant="body2">
            End: {formatTimestamp(run.end_time)}
          </Typography>
        </Box>
      }
      arrow
      placement="top"
    >
      <Box
        onClick={onClick}
        sx={{
          width: 32,
          height: 32,
          borderRadius: 1,
          bgcolor: color,
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          '&:hover': {
            transform: 'scale(1.15)',
            boxShadow: 2,
          },
        }}
      />
    </Tooltip>
  );
};

const MatrixView: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [matrixData, setMatrixData] = useState<MatrixData | null>(null);
  const [days, setDays] = useState(7);
  const [runsPerJob, setRunsPerJob] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getJobsMatrix(days, runsPerJob);
        setMatrixData(data);
      } catch (err) {
        console.error('Failed to fetch matrix data:', err);
        setError('Failed to load matrix data. Please try again.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [days, runsPerJob]);

  const filteredJobs = useMemo(() => {
    if (!matrixData?.jobs) return [];
    if (!searchTerm.trim()) return matrixData.jobs;

    const lowerSearch = searchTerm.toLowerCase();
    return matrixData.jobs.filter(
      (job) =>
        (job.job_name?.toLowerCase().includes(lowerSearch)) ||
        (job.job_id?.toLowerCase().includes(lowerSearch))
    );
  }, [matrixData, searchTerm]);

  const handleRunClick = (jobId: string | null, runId: string | null) => {
    if (jobId && runId) {
      // Navigate to job run details - can be customized based on routing setup
      navigate(`/jobs?job_id=${jobId}&run_id=${runId}`);
    }
  };

  const summaryStats = useMemo(() => {
    if (!matrixData?.jobs) return { total: 0, success: 0, failed: 0, running: 0 };

    let success = 0;
    let failed = 0;
    let running = 0;
    let total = 0;

    matrixData.jobs.forEach((job) => {
      job.runs.forEach((run) => {
        if (run) {
          total++;
          const state = run.result_state;
          if (state === 'SUCCESS') success++;
          else if (state === 'FAILED') failed++;
          else if (state === 'RUNNING') running++;
        }
      });
    });

    return { total, success, failed, running };
  }, [matrixData]);

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight="bold" gutterBottom>
            Matrix View
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Visual grid of job run history - hover for details, click to navigate
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Days</InputLabel>
            <Select
              value={days}
              label="Days"
              onChange={(e) => setDays(Number(e.target.value))}
            >
              <MenuItem value={1}>1 Day</MenuItem>
              <MenuItem value={3}>3 Days</MenuItem>
              <MenuItem value={7}>7 Days</MenuItem>
              <MenuItem value={14}>14 Days</MenuItem>
              <MenuItem value={30}>30 Days</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 120 }}>
            <InputLabel>Runs</InputLabel>
            <Select
              value={runsPerJob}
              label="Runs"
              onChange={(e) => setRunsPerJob(Number(e.target.value))}
            >
              <MenuItem value={10}>10 runs</MenuItem>
              <MenuItem value={20}>20 runs</MenuItem>
              <MenuItem value={50}>50 runs</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </Box>

      {/* Summary Stats */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Paper sx={{ px: 2, py: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <GridViewIcon color="primary" />
          <Typography variant="body2">
            <strong>{filteredJobs.length}</strong> Jobs
          </Typography>
        </Paper>
        <Paper sx={{ px: 2, py: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: statusColors.SUCCESS }} />
          <Typography variant="body2">
            <strong>{summaryStats.success}</strong> Success
          </Typography>
        </Paper>
        <Paper sx={{ px: 2, py: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: statusColors.FAILED }} />
          <Typography variant="body2">
            <strong>{summaryStats.failed}</strong> Failed
          </Typography>
        </Paper>
        <Paper sx={{ px: 2, py: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 12, height: 12, borderRadius: 0.5, bgcolor: statusColors.RUNNING }} />
          <Typography variant="body2">
            <strong>{summaryStats.running}</strong> Running
          </Typography>
        </Paper>
      </Box>

      {/* Search */}
      <Paper sx={{ p: 2, mb: 3, borderRadius: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search by job name or ID..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      {/* Matrix Grid */}
      <Paper sx={{ p: 3, borderRadius: 3, overflow: 'hidden' }}>
        {error ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : loading ? (
          <Box>
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} variant="rectangular" height={40} sx={{ mb: 1, borderRadius: 1 }} />
            ))}
          </Box>
        ) : filteredJobs.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">
              {searchTerm ? 'No jobs match your search' : 'No job data available'}
            </Typography>
          </Box>
        ) : (
          <Box sx={{ overflowX: 'auto' }}>
            {/* Column Headers */}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                mb: 2,
                pb: 1,
                borderBottom: 1,
                borderColor: 'divider',
              }}
            >
              <Box sx={{ width: 200, flexShrink: 0, pr: 2 }}>
                <Typography variant="caption" fontWeight="bold" color="text.secondary">
                  JOB NAME
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                  MOST RECENT
                </Typography>
                {[...Array(Math.min(runsPerJob, 10))].map((_, i) => (
                  <Box key={i} sx={{ width: 32, textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">
                      {i === 0 ? 'Latest' : ''}
                    </Typography>
                  </Box>
                ))}
                {runsPerJob > 10 && (
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                    ... OLDER
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Job Rows */}
            {filteredJobs.map((job) => (
              <Box
                key={job.job_id || job.job_name}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  py: 1,
                  '&:hover': { bgcolor: 'action.hover' },
                  borderRadius: 1,
                }}
              >
                {/* Job Name Column */}
                <Box sx={{ width: 200, flexShrink: 0, pr: 2 }}>
                  <Tooltip title={`Job ID: ${job.job_id || 'N/A'}`}>
                    <Typography
                      variant="body2"
                      noWrap
                      sx={{
                        fontWeight: 500,
                        cursor: 'pointer',
                        '&:hover': { color: 'primary.main' },
                      }}
                      onClick={() => navigate(`/jobs?job_id=${job.job_id}`)}
                    >
                      {job.job_name || 'Unknown Job'}
                    </Typography>
                  </Tooltip>
                </Box>

                {/* Run Cells */}
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  {job.runs.map((run, idx) => (
                    <RunCell
                      key={run?.run_id || `empty-${idx}`}
                      run={run}
                      onClick={() => handleRunClick(job.job_id, run?.run_id || null)}
                    />
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        )}

        {/* Legend */}
        <Box sx={{ display: 'flex', gap: 3, mt: 3, pt: 2, borderTop: 1, borderColor: 'divider', flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
            Legend:
          </Typography>
          {Object.entries(statusColors).filter(([key]) => key !== 'UNKNOWN').map(([status, color]) => (
            <Box key={status} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 16, height: 16, borderRadius: 0.5, bgcolor: color }} />
              <Typography variant="caption">{status}</Typography>
            </Box>
          ))}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 16, height: 16, borderRadius: 0.5, bgcolor: 'action.disabledBackground' }} />
            <Typography variant="caption">No Data</Typography>
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default MatrixView;
