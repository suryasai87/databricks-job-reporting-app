import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  CardActions,
  Button,
  TextField,
  Alert,
  CircularProgress,
  Chip,
  Divider,
} from '@mui/material';
import {
  Assessment as ReportIcon,
  TrendingUp as PerformanceIcon,
  AttachMoney as CostIcon,
  HealthAndSafety as HealthIcon,
  Download as DownloadIcon,
  Schedule as ScheduleIcon,
  Email as EmailIcon,
} from '@mui/icons-material';
import { generateReport } from '../services/api';

interface ReportType {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const reportTypes: ReportType[] = [
  {
    id: 'performance',
    name: 'Performance Report',
    description: 'Job execution times, success rates, and performance trends over time.',
    icon: <PerformanceIcon />,
    color: '#2196f3',
  },
  {
    id: 'cost',
    name: 'Cost Analysis Report',
    description: 'Detailed cost breakdown by job, user, and time period with recommendations.',
    icon: <CostIcon />,
    color: '#9c27b0',
  },
  {
    id: 'health',
    name: 'Health & Anomaly Report',
    description: 'Failed jobs, anomalies, prolonged runs, and retry statistics.',
    icon: <HealthIcon />,
    color: '#f44336',
  },
  {
    id: 'executive',
    name: 'Executive Summary',
    description: 'High-level overview of all metrics for stakeholder presentations.',
    icon: <ReportIcon />,
    color: '#ff9800',
  },
];

const Reports: React.FC = () => {
  const [selectedReport, setSelectedReport] = useState<string>('');
  const [startDate, setStartDate] = useState<string>(
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]
  );
  const [endDate, setEndDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [generating, setGenerating] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!selectedReport) {
      setError('Please select a report type');
      return;
    }

    setGenerating(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await generateReport(selectedReport, startDate, endDate);
      setSuccess(`Report generated successfully! Report ID: ${result.report_id}`);
    } catch (err) {
      console.error('Failed to generate report:', err);
      setError('Failed to generate report. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Reports
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Generate comprehensive reports on job performance, costs, and health
        </Typography>
      </Box>

      {/* Report Types */}
      <Typography variant="h6" gutterBottom>
        Select Report Type
      </Typography>
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {reportTypes.map((report) => (
          <Grid item xs={12} sm={6} md={3} key={report.id}>
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
              <Card
                onClick={() => setSelectedReport(report.id)}
                sx={{
                  cursor: 'pointer',
                  height: '100%',
                  border: selectedReport === report.id ? 2 : 1,
                  borderColor: selectedReport === report.id ? report.color : 'divider',
                  bgcolor:
                    selectedReport === report.id ? `${report.color}10` : 'background.paper',
                  transition: 'all 0.2s',
                }}
              >
                <CardContent>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      mb: 2,
                      color: report.color,
                    }}
                  >
                    {report.icon}
                    <Typography variant="h6" fontWeight={600}>
                      {report.name}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    {report.description}
                  </Typography>
                </CardContent>
                {selectedReport === report.id && (
                  <CardActions sx={{ justifyContent: 'flex-end', pt: 0 }}>
                    <Chip label="Selected" color="primary" size="small" />
                  </CardActions>
                )}
              </Card>
            </motion.div>
          </Grid>
        ))}
      </Grid>

      {/* Report Configuration */}
      <Paper sx={{ p: 3, borderRadius: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Report Configuration
        </Typography>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Start Date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="End Date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <Button
              variant="contained"
              size="large"
              fullWidth
              onClick={handleGenerate}
              disabled={generating || !selectedReport}
              startIcon={generating ? <CircularProgress size={20} /> : <DownloadIcon />}
            >
              {generating ? 'Generating...' : 'Generate Report'}
            </Button>
          </Grid>
        </Grid>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        {success && (
          <Alert severity="success" sx={{ mt: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}
      </Paper>

      {/* Scheduled Reports */}
      <Paper sx={{ p: 3, borderRadius: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="h6">Scheduled Reports</Typography>
            <Typography variant="body2" color="text.secondary">
              Configure automated report generation and delivery
            </Typography>
          </Box>
          <Button variant="outlined" startIcon={<ScheduleIcon />}>
            Schedule New
          </Button>
        </Box>
        <Divider sx={{ mb: 2 }} />
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <ScheduleIcon sx={{ fontSize: 60, color: 'grey.400', mb: 2 }} />
          <Typography variant="body1" color="text.secondary" gutterBottom>
            No scheduled reports configured
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Set up automated reports to be delivered via email on a recurring schedule
          </Typography>
        </Box>

        {/* Quick Actions */}
        <Divider sx={{ my: 3 }} />
        <Typography variant="subtitle2" gutterBottom>
          Quick Actions
        </Typography>
        <Grid container spacing={2}>
          <Grid item>
            <Button variant="outlined" size="small" startIcon={<EmailIcon />}>
              Configure Email Delivery
            </Button>
          </Grid>
          <Grid item>
            <Button variant="outlined" size="small" startIcon={<ScheduleIcon />}>
              Set Weekly Summary
            </Button>
          </Grid>
          <Grid item>
            <Button variant="outlined" size="small" startIcon={<HealthIcon />}>
              Enable Health Alerts
            </Button>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default Reports;
