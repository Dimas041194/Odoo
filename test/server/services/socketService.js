const jwt = require('jsonwebtoken');
const User = require('../models/User');

// Store active connections
const activeConnections = new Map();

const initializeSocket = (io) => {
  // Authentication middleware for Socket.IO
  io.use(async (socket, next) => {
    try {
      const token = socket.handshake.auth.token || socket.handshake.headers.authorization?.split(' ')[1];
      
      if (!token) {
        return next(new Error('Authentication error: No token provided'));
      }

      const decoded = jwt.verify(token, process.env.JWT_SECRET);
      const user = await User.findById(decoded.userId).select('-password');
      
      if (!user || !user.isActive) {
        return next(new Error('Authentication error: Invalid user'));
      }

      socket.userId = user._id.toString();
      socket.user = user;
      next();
    } catch (error) {
      next(new Error('Authentication error: Invalid token'));
    }
  });

  io.on('connection', (socket) => {
    console.log(`User ${socket.user.username} connected with socket ${socket.id}`);
    
    // Store connection
    activeConnections.set(socket.userId, {
      socketId: socket.id,
      user: socket.user,
      connectedAt: new Date(),
      lastActivity: new Date()
    });

    // Join user to their personal room
    socket.join(`user_${socket.userId}`);

    // Send connection confirmation
    socket.emit('connected', {
      message: 'Connected to Advanced Matrix System',
      userId: socket.userId,
      timestamp: new Date()
    });

    // Handle matrix updates
    socket.on('matrix_update', async (data) => {
      try {
        const { matrixId, changes, operation } = data;
        
        // Update last activity
        const connection = activeConnections.get(socket.userId);
        if (connection) {
          connection.lastActivity = new Date();
        }

        // Broadcast to other collaborators
        socket.to(`matrix_${matrixId}`).emit('matrix_updated', {
          matrixId,
          changes,
          operation,
          updatedBy: {
            id: socket.userId,
            username: socket.user.username,
            fullName: socket.user.fullName
          },
          timestamp: new Date()
        });

        // Send confirmation back to sender
        socket.emit('matrix_update_confirmed', {
          matrixId,
          timestamp: new Date()
        });
      } catch (error) {
        console.error('Matrix update error:', error);
        socket.emit('error', { message: 'Failed to update matrix' });
      }
    });

    // Handle joining matrix room
    socket.on('join_matrix', async (data) => {
      try {
        const { matrixId } = data;
        
        // Verify user has access to matrix
        const Matrix = require('../models/Matrix');
        const matrix = await Matrix.findById(matrixId);
        
        if (!matrix) {
          socket.emit('error', { message: 'Matrix not found' });
          return;
        }

        // Check permissions
        if (!matrix.hasPermission(socket.userId, 'view')) {
          socket.emit('error', { message: 'Access denied' });
          return;
        }

        // Join matrix room
        socket.join(`matrix_${matrixId}`);
        
        // Notify others in the room
        socket.to(`matrix_${matrixId}`).emit('user_joined_matrix', {
          matrixId,
          user: {
            id: socket.userId,
            username: socket.user.username,
            fullName: socket.user.fullName
          },
          timestamp: new Date()
        });

        socket.emit('joined_matrix', {
          matrixId,
          message: `Joined matrix "${matrix.name}"`,
          timestamp: new Date()
        });
      } catch (error) {
        console.error('Join matrix error:', error);
        socket.emit('error', { message: 'Failed to join matrix' });
      }
    });

    // Handle leaving matrix room
    socket.on('leave_matrix', (data) => {
      const { matrixId } = data;
      socket.leave(`matrix_${matrixId}`);
      
      // Notify others in the room
      socket.to(`matrix_${matrixId}`).emit('user_left_matrix', {
        matrixId,
        user: {
          id: socket.userId,
          username: socket.user.username,
          fullName: socket.user.fullName
        },
        timestamp: new Date()
      });
    });

    // Handle real-time collaboration
    socket.on('cell_edit', (data) => {
      const { matrixId, row, col, value, isEditing } = data;
      
      // Broadcast to other users in the same matrix
      socket.to(`matrix_${matrixId}`).emit('cell_being_edited', {
        matrixId,
        row,
        col,
        value,
        isEditing,
        editor: {
          id: socket.userId,
          username: socket.user.username,
          fullName: socket.user.fullName
        },
        timestamp: new Date()
      });
    });

    // Handle cursor position
    socket.on('cursor_position', (data) => {
      const { matrixId, row, col } = data;
      
      socket.to(`matrix_${matrixId}`).emit('user_cursor', {
        matrixId,
        row,
        col,
        user: {
          id: socket.userId,
          username: socket.user.username,
          fullName: socket.user.fullName
        },
        timestamp: new Date()
      });
    });

    // Handle typing indicators
    socket.on('typing_start', (data) => {
      const { matrixId, commentId } = data;
      
      socket.to(`matrix_${matrixId}`).emit('user_typing', {
        matrixId,
        commentId,
        user: {
          id: socket.userId,
          username: socket.user.username,
          fullName: socket.user.fullName
        },
        timestamp: new Date()
      });
    });

    socket.on('typing_stop', (data) => {
      const { matrixId, commentId } = data;
      
      socket.to(`matrix_${matrixId}`).emit('user_stopped_typing', {
        matrixId,
        commentId,
        user: {
          id: socket.userId,
          username: socket.user.username
        },
        timestamp: new Date()
      });
    });

    // Handle notifications
    socket.on('notification_read', async (data) => {
      try {
        const { notificationId } = data;
        const { markAsRead } = require('./notificationService');
        await markAsRead(notificationId, socket.userId);
        
        socket.emit('notification_marked_read', {
          notificationId,
          timestamp: new Date()
        });
      } catch (error) {
        console.error('Notification read error:', error);
        socket.emit('error', { message: 'Failed to mark notification as read' });
      }
    });

    // Handle ping/pong for connection health
    socket.on('ping', () => {
      socket.emit('pong', { timestamp: new Date() });
    });

    // Handle disconnection
    socket.on('disconnect', (reason) => {
      console.log(`User ${socket.user.username} disconnected: ${reason}`);
      
      // Remove from active connections
      activeConnections.delete(socket.userId);
      
      // Notify all matrix rooms the user was in
      socket.rooms.forEach(room => {
        if (room.startsWith('matrix_')) {
          socket.to(room).emit('user_disconnected', {
            user: {
              id: socket.userId,
              username: socket.user.username,
              fullName: socket.user.fullName
            },
            timestamp: new Date()
          });
        }
      });
    });
  });

  // Periodic cleanup of inactive connections
  setInterval(() => {
    const now = new Date();
    const inactiveThreshold = 30 * 60 * 1000; // 30 minutes
    
    for (const [userId, connection] of activeConnections.entries()) {
      if (now - connection.lastActivity > inactiveThreshold) {
        console.log(`Removing inactive connection for user ${userId}`);
        activeConnections.delete(userId);
      }
    }
  }, 5 * 60 * 1000); // Check every 5 minutes
};

// Send notification to specific user
const sendNotificationToUser = (userId, notification) => {
  const connection = activeConnections.get(userId);
  if (connection) {
    const io = require('../index').io;
    io.to(`user_${userId}`).emit('new_notification', notification);
  }
};

// Send notification to matrix collaborators
const sendNotificationToMatrix = (matrixId, notification) => {
  const io = require('../index').io;
  io.to(`matrix_${matrixId}`).emit('matrix_notification', notification);
};

// Get active users count
const getActiveUsersCount = () => {
  return activeConnections.size;
};

// Get active users list
const getActiveUsers = () => {
  return Array.from(activeConnections.values()).map(conn => ({
    id: conn.user._id,
    username: conn.user.username,
    fullName: conn.user.fullName,
    connectedAt: conn.connectedAt,
    lastActivity: conn.lastActivity
  }));
};

module.exports = {
  initializeSocket,
  sendNotificationToUser,
  sendNotificationToMatrix,
  getActiveUsersCount,
  getActiveUsers
};

