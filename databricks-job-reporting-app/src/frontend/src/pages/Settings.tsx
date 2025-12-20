import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Grid,
  Alert,
  Card,
  CardContent,
  Chip,
  CircularProgress,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Psychology as GenieIcon,
} from '@mui/icons-material';
import { getAuthStatus, getGenieSpaces } from '../services/api';
import type { User } from '../types';

const Settings: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [genieSpaces, setGenieSpaces] = useState<any[]>([]);
  const [selectedGenieSpace, setSelectedGenieSpace] = useState('');
  const [settings, setSettings] = useState({
    refreshInterval: 30,
    enableNotifications: true,
    warningThreshold: 60,
    criticalThreshold: 180,
    anomalyWarningZ: 2.0,
    anomalyCriticalZ: 3.0,
    defaultDays: 7,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [userData, spaces] = await Promise.all([
          getAuthStatus(),
          getGenieSpaces(),
        ]);
        setUser(userData);
        setGenieSpaces(spaces);
        if (spaces.length > 0) {
          setSelectedGenieSpace(spaces[0].id);
        }
      } catch (error) {
        console.error('Failed to fetch settings data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSave = () => {
    // In a real app, this would save to localStorage or backend
    localStorage.setItem('jobsMonitorSettings', JSON.stringify(settings));
    localStorage.setItem('selectedGenieSpace', selectedGenieSpace);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure application preferences and thresholds
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Authentication Status */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Authentication Status
            </Typography>
            <Card
              sx={{
                bgcolor: user?.authenticated ? 'success.dark' : 'warning.dark',
                color: 'white',
                mb: 2,
              }}
            >
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  {user?.authenticated ? (
                    <CheckIcon sx={{ fontSize: 40 }} />
                  ) : (
                    <ErrorIcon sx={{ fontSize: 40 }} />
                  )}
                  <Box>
                    <Typography variant="h6">
                      {user?.authenticated ? 'Authenticated' : 'Not Authenticated'}
                    </Typography>
                    <Typography variant="body2">
                      {user?.email || 'No user information'}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Chip label={`Source: ${user?.source || 'N/A'}`} variant="outlined" />
              {user?.name && <Chip label={`Name: ${user.name}`} variant="outlined" />}
            </Box>
          </Paper>
        </Grid>

        {/* Genie Space Configuration */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <GenieIcon color="primary" />
              <Typography variant="h6">AI Assistant Configuration</Typography>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Select the Genie Space for AI-powered insights
            </Typography>
            {genieSpaces.length > 0 ? (
              <Box>
                {genieSpaces.map((space) => (
                  <Card
                    key={space.id}
                    onClick={() => setSelectedGenieSpace(space.id)}
                    sx={{
                      mb: 1,
                      cursor: 'pointer',
                      border: selectedGenieSpace === space.id ? 2 : 1,
                      borderColor: selectedGenieSpace === space.id ? 'primary.main' : 'divider',
                      bgcolor:
                        selectedGenieSpace === space.id ? 'primary.dark' : 'background.default',
                    }}
                  >
                    <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body1" fontWeight={500}>
                          {space.name}
                        </Typography>
                        {selectedGenieSpace === space.id && (
                          <Chip label="Selected" size="small" color="primary" />
                        )}
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        ID: {space.id}
                      </Typography>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            ) : (
              <Alert severity="warning">
                No Genie Spaces found. Please create a Genie Space in Databricks to enable AI features.
              </Alert>
            )}
          </Paper>
        </Grid>

        {/* Display Settings */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Display Settings
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Default Time Range (days)"
                  type="number"
                  value={settings.defaultDays}
                  onChange={(e) =>
                    setSettings({ ...settings, defaultDays: Number(e.target.value) })
                  }
                  inputProps={{ min: 1, max: 90 }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Auto-refresh Interval (seconds)"
                  type="number"
                  value={settings.refreshInterval}
                  onChange={(e) =>
                    setSettings({ ...settings, refreshInterval: Number(e.target.value) })
                  }
                  inputProps={{ min: 10, max: 300 }}
                />
              </Grid>
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.enableNotifications}
                      onChange={(e) =>
                        setSettings({ ...settings, enableNotifications: e.target.checked })
                      }
                    />
                  }
                  label="Enable Browser Notifications"
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Threshold Settings */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="h6" gutterBottom>
              Alert Thresholds
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Warning (minutes)"
                  type="number"
                  value={settings.warningThreshold}
                  onChange={(e) =>
                    setSettings({ ...settings, warningThreshold: Number(e.target.value) })
                  }
                  inputProps={{ min: 10 }}
                  helperText="Prolonged job warning"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Critical (minutes)"
                  type="number"
                  value={settings.criticalThreshold}
                  onChange={(e) =>
                    setSettings({ ...settings, criticalThreshold: Number(e.target.value) })
                  }
                  inputProps={{ min: 30 }}
                  helperText="Prolonged job critical"
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Anomaly Warning (Z-score)"
                  type="number"
                  value={settings.anomalyWarningZ}
                  onChange={(e) =>
                    setSettings({ ...settings, anomalyWarningZ: Number(e.target.value) })
                  }
                  inputProps={{ min: 1, max: 5, step: 0.1 }}
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  fullWidth
                  label="Anomaly Critical (Z-score)"
                  type="number"
                  value={settings.anomalyCriticalZ}
                  onChange={(e) =>
                    setSettings({ ...settings, anomalyCriticalZ: Number(e.target.value) })
                  }
                  inputProps={{ min: 2, max: 5, step: 0.1 }}
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Save Button */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
            {saved && (
              <Alert severity="success" sx={{ flexGrow: 1 }}>
                Settings saved successfully!
              </Alert>
            )}
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => window.location.reload()}
            >
              Reset
            </Button>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
            >
              Save Settings
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Settings;
