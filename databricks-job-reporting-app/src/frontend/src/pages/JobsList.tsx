import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  TableSortLabel,
  Chip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
  Skeleton,
  InputAdornment,
  Grid,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  CheckCircle as SuccessIcon,
  Error as FailedIcon,
  PlayArrow as RunningIcon,
  Cancel as CancelledIcon,
  Schedule as PendingIcon,
} from '@mui/icons-material';
import { getJobRuns } from '../services/api';
import type { JobRun } from '../types';

type Order = 'asc' | 'desc';

const statusIcons: Record<string, React.ReactNode> = {
  SUCCESS: <SuccessIcon sx={{ color: 'success.main', fontSize: 18 }} />,
  FAILED: <FailedIcon sx={{ color: 'error.main', fontSize: 18 }} />,
  RUNNING: <RunningIcon sx={{ color: 'warning.main', fontSize: 18 }} />,
  CANCELLED: <CancelledIcon sx={{ color: 'grey.500', fontSize: 18 }} />,
  PENDING: <PendingIcon sx={{ color: 'info.main', fontSize: 18 }} />,
};

const statusColors: Record<string, 'success' | 'error' | 'warning' | 'default' | 'info'> = {
  SUCCESS: 'success',
  FAILED: 'error',
  RUNNING: 'warning',
  CANCELLED: 'default',
  PENDING: 'info',
};

const runTypeColors: Record<string, string> = {
  JOB_RUN: '#2196f3',
  SUBMIT_RUN: '#9c27b0',
  WORKFLOW_RUN: '#ff9800',
};

const formatDuration = (seconds: number | null): string => {
  if (seconds === null) return '-';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
};

const formatDateTime = (dateStr: string): string => {
  const date = new Date(dateStr);
  return date.toLocaleString();
};

const JobsList: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [orderBy, setOrderBy] = useState<keyof JobRun>('start_time');
  const [order, setOrder] = useState<Order>('desc');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [daysFilter, setDaysFilter] = useState<number>(7);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const data = await getJobRuns(daysFilter, 1000);
      setJobs(data);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [daysFilter]);

  const handleSort = (property: keyof JobRun) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const matchesSearch =
        job.job_name.toLowerCase().includes(search.toLowerCase()) ||
        job.job_id.includes(search) ||
        job.run_id.includes(search);
      const matchesStatus =
        statusFilter === 'all' || job.result_state === statusFilter;
      const matchesType = typeFilter === 'all' || job.run_type === typeFilter;
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [jobs, search, statusFilter, typeFilter]);

  const sortedJobs = useMemo(() => {
    return [...filteredJobs].sort((a, b) => {
      const aVal = a[orderBy];
      const bVal = b[orderBy];
      if (aVal === null) return 1;
      if (bVal === null) return -1;
      if (aVal < bVal) return order === 'asc' ? -1 : 1;
      if (aVal > bVal) return order === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredJobs, orderBy, order]);

  const paginatedJobs = useMemo(() => {
    return sortedJobs.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
  }, [sortedJobs, page, rowsPerPage]);

  const uniqueStatuses = useMemo(() => {
    return Array.from(new Set(jobs.map((j) => j.result_state).filter(Boolean)));
  }, [jobs]);

  const uniqueTypes = useMemo(() => {
    return Array.from(new Set(jobs.map((j) => j.run_type).filter(Boolean)));
  }, [jobs]);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Jobs List
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Browse and filter all job runs with detailed information
        </Typography>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3, borderRadius: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search by job name, ID, or run ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="all">All Statuses</MenuItem>
                {uniqueStatuses.map((status) => (
                  <MenuItem key={status} value={status}>
                    {status}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Run Type</InputLabel>
              <Select
                value={typeFilter}
                label="Run Type"
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <MenuItem value="all">All Types</MenuItem>
                {uniqueTypes.map((type) => (
                  <MenuItem key={type} value={type}>
                    {type}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Time Range</InputLabel>
              <Select
                value={daysFilter}
                label="Time Range"
                onChange={(e) => setDaysFilter(Number(e.target.value))}
              >
                <MenuItem value={1}>Last 24 Hours</MenuItem>
                <MenuItem value={7}>Last 7 Days</MenuItem>
                <MenuItem value={14}>Last 14 Days</MenuItem>
                <MenuItem value={30}>Last 30 Days</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6} md={2}>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchJobs} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Chip
              label={`${filteredJobs.length} jobs`}
              size="small"
              color="primary"
              variant="outlined"
            />
          </Grid>
        </Grid>
      </Paper>

      {/* Table */}
      <Paper sx={{ borderRadius: 2, overflow: 'hidden' }}>
        <TableContainer sx={{ maxHeight: 'calc(100vh - 380px)' }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'job_name'}
                    direction={orderBy === 'job_name' ? order : 'asc'}
                    onClick={() => handleSort('job_name')}
                  >
                    Job Name
                  </TableSortLabel>
                </TableCell>
                <TableCell>Run Type</TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'result_state'}
                    direction={orderBy === 'result_state' ? order : 'asc'}
                    onClick={() => handleSort('result_state')}
                  >
                    Status
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'start_time'}
                    direction={orderBy === 'start_time' ? order : 'asc'}
                    onClick={() => handleSort('start_time')}
                  >
                    Start Time
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'duration_seconds'}
                    direction={orderBy === 'duration_seconds' ? order : 'asc'}
                    onClick={() => handleSort('duration_seconds')}
                  >
                    Duration
                  </TableSortLabel>
                </TableCell>
                <TableCell>Trigger</TableCell>
                <TableCell>Run As</TableCell>
                <TableCell align="right">Cost</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <TableCell key={j}>
                        <Skeleton />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : paginatedJobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">No jobs found</Typography>
                  </TableCell>
                </TableRow>
              ) : (
                paginatedJobs.map((job) => (
                  <motion.tr
                    key={`${job.job_id}-${job.run_id}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    component={TableRow}
                    sx={{
                      '&:hover': { bgcolor: 'action.hover' },
                      cursor: 'pointer',
                    }}
                  >
                    <TableCell>
                      <Box>
                        <Typography variant="body2" fontWeight={500}>
                          {job.job_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          ID: {job.job_id} | Run: {job.run_id}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={job.run_type}
                        size="small"
                        sx={{
                          bgcolor: `${runTypeColors[job.run_type] || '#666'}20`,
                          color: runTypeColors[job.run_type] || '#666',
                          fontWeight: 500,
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {statusIcons[job.result_state || 'PENDING']}
                        <Chip
                          label={job.result_state || 'PENDING'}
                          size="small"
                          color={statusColors[job.result_state || 'PENDING']}
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatDateTime(job.start_time)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatDuration(job.duration_seconds)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={job.trigger_type}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
                        {job.run_as}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" fontWeight={500}>
                        {job.cost_usd ? `$${job.cost_usd.toFixed(2)}` : '-'}
                      </Typography>
                    </TableCell>
                  </motion.tr>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={filteredJobs.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </Paper>
    </Box>
  );
};

export default JobsList;
