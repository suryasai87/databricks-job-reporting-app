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
  Alert,
  Tooltip,
  TextField,
  InputAdornment,
} from '@mui/material';
import {
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  CloudQueue as ClusterIcon,
  Search as SearchIcon,
} from '@mui/icons-material';
import { getClusterConfigs } from '../services/api';
import type { ClusterConfig } from '../types';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';

const COLORS = ['#FF3621', '#2196f3', '#4caf50', '#ff9800', '#9c27b0', '#00bcd4'];

const clusterTypeColors: Record<string, string> = {
  'jobs-cluster': '#2196f3',
  'all-purpose': '#4caf50',
  'sql-warehouse': '#9c27b0',
  serverless: '#ff9800',
  'job-cluster': '#2196f3',
};

const ClusterAnalysis: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [clusters, setClusters] = useState<ClusterConfig[]>([]);
  const [search, setSearch] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const data = await getClusterConfigs();
        setClusters(data);
      } catch (error) {
        console.error('Failed to fetch cluster configs:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const filteredClusters = clusters.filter((c) => {
    const searchLower = search.toLowerCase();
    return (
      (c.cluster_name || '').toLowerCase().includes(searchLower) ||
      (c.cluster_id || '').includes(search) ||
      (c.cluster_type || '').toLowerCase().includes(searchLower) ||
      (c.job_name || '').toLowerCase().includes(searchLower)
    );
  });

  const clustersByType = clusters.reduce((acc, c) => {
    const type = c.cluster_type || 'unknown';
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const typeChartData = Object.entries(clustersByType).map(([name, value]) => ({
    name,
    value,
  }));

  const dbrVersions = clusters.reduce((acc, c) => {
    const version = c.dbr_version || 'N/A';
    acc[version] = (acc[version] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const versionChartData = Object.entries(dbrVersions)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  const uniqueDriverTypes = [...new Set(clusters.map((c) => c.driver_node_type).filter(Boolean))].length;
  const uniqueWorkerTypes = [...new Set(clusters.map((c) => c.worker_node_type).filter(Boolean))].length;

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Cluster Analysis
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Analyze cluster configurations and resource utilization
        </Typography>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <motion.div whileHover={{ scale: 1.02 }}>
            <Card sx={{ bgcolor: 'primary.dark', color: 'white' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Box>
                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                      Total Clusters
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : clusters.length}
                    </Typography>
                  </Box>
                  <ClusterIcon sx={{ fontSize: 40, opacity: 0.8 }} />
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
                      Cluster Types
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : Object.keys(clustersByType).length}
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
                      Driver Node Types
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : uniqueDriverTypes}
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
                      Worker Node Types
                    </Typography>
                    <Typography variant="h4" fontWeight="bold">
                      {loading ? <Skeleton width={40} /> : uniqueWorkerTypes}
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
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
            <Typography variant="h6" gutterBottom>
              Clusters by Type
            </Typography>
            {loading ? (
              <Skeleton variant="circular" width={250} height={250} sx={{ mx: 'auto' }} />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={typeChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                  >
                    {typeChartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={clusterTypeColors[entry.name] || COLORS[index % COLORS.length]}
                      />
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
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3, height: 350 }}>
            <Typography variant="h6" gutterBottom>
              DBR Version Distribution
            </Typography>
            {loading ? (
              <Skeleton variant="rectangular" height={280} />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={versionChartData} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis type="number" stroke="#888" />
                  <YAxis type="category" dataKey="name" stroke="#888" width={70} tick={{ fontSize: 11 }} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #333',
                      borderRadius: 8,
                    }}
                  />
                  <Bar dataKey="value" fill="#2196f3" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Cluster Table */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Cluster Configurations</Typography>
          <TextField
            size="small"
            placeholder="Search clusters..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ width: 300 }}
          />
        </Box>
        {loading ? (
          <Skeleton variant="rectangular" height={400} />
        ) : filteredClusters.length === 0 ? (
          <Alert severity="info">No clusters found matching your search.</Alert>
        ) : (
          <TableContainer sx={{ maxHeight: 500 }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Cluster Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Driver Node</TableCell>
                  <TableCell>Worker Node</TableCell>
                  <TableCell>Workers</TableCell>
                  <TableCell>DBR Version</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredClusters.map((cluster, index) => (
                  <TableRow key={cluster.cluster_id || `cluster-${index}`} hover>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" fontWeight={500}>
                          {cluster.cluster_name || cluster.job_name || 'Unknown'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {cluster.cluster_id || cluster.warehouse_id || '-'}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={cluster.cluster_type || 'N/A'}
                        size="small"
                        sx={{
                          bgcolor: `${clusterTypeColors[cluster.cluster_type || ''] || '#666'}20`,
                          color: clusterTypeColors[cluster.cluster_type || ''] || '#666',
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Driver Node Type">
                        <Typography variant="body2">{cluster.driver_node_type || '-'}</Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Worker Node Type">
                        <Typography variant="body2">{cluster.worker_node_type || '-'}</Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      {cluster.fixed_workers != null ? (
                        <Chip label={`Fixed: ${cluster.fixed_workers}`} size="small" />
                      ) : cluster.run_type ? (
                        <Chip label={cluster.run_type} size="small" color="info" variant="outlined" />
                      ) : (
                        <Chip
                          label={`${cluster.min_workers || 0}-${cluster.max_workers || 'N/A'}`}
                          size="small"
                          color="info"
                          variant="outlined"
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip label={cluster.dbr_version || 'N/A'} size="small" variant="outlined" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
};

export default ClusterAnalysis;
