const mongoose = require('mongoose');

const notificationSchema = new mongoose.Schema({
  user: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  type: {
    type: String,
    enum: [
      'matrix_created',
      'matrix_updated',
      'matrix_shared',
      'matrix_comment',
      'collaborator_added',
      'collaborator_removed',
      'system_alert',
      'email_verification',
      'password_reset',
      'welcome'
    ],
    required: true
  },
  title: {
    type: String,
    required: true,
    maxlength: 200
  },
  message: {
    type: String,
    required: true,
    maxlength: 1000
  },
  data: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  },
  isRead: {
    type: Boolean,
    default: false
  },
  isEmailSent: {
    type: Boolean,
    default: false
  },
  emailSentAt: Date,
  priority: {
    type: String,
    enum: ['low', 'medium', 'high', 'urgent'],
    default: 'medium'
  },
  expiresAt: Date,
  actions: [{
    label: String,
    url: String,
    action: String
  }],
  createdAt: {
    type: Date,
    default: Date.now
  },
  readAt: Date
}, {
  timestamps: true
});

// Indexes for better performance
notificationSchema.index({ user: 1, isRead: 1 });
notificationSchema.index({ user: 1, createdAt: -1 });
notificationSchema.index({ type: 1 });
notificationSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

// Static method to create notification
notificationSchema.statics.createNotification = async function(userId, type, title, message, data = {}, options = {}) {
  const notification = new this({
    user: userId,
    type,
    title,
    message,
    data,
    priority: options.priority || 'medium',
    expiresAt: options.expiresAt,
    actions: options.actions || []
  });
  
  return await notification.save();
};

// Static method to get user notifications
notificationSchema.statics.getUserNotifications = async function(userId, options = {}) {
  const {
    page = 1,
    limit = 20,
    unreadOnly = false,
    type = null
  } = options;
  
  const query = { user: userId };
  if (unreadOnly) query.isRead = false;
  if (type) query.type = type;
  
  const notifications = await this.find(query)
    .populate('user', 'username firstName lastName avatar')
    .sort({ createdAt: -1 })
    .skip((page - 1) * limit)
    .limit(limit);
    
  const total = await this.countDocuments(query);
  
  return {
    notifications,
    pagination: {
      page,
      limit,
      total,
      pages: Math.ceil(total / limit)
    }
  };
};

// Method to mark as read
notificationSchema.methods.markAsRead = function() {
  this.isRead = true;
  this.readAt = new Date();
  return this.save();
};

// Method to mark as unread
notificationSchema.methods.markAsUnread = function() {
  this.isRead = false;
  this.readAt = undefined;
  return this.save();
};

module.exports = mongoose.model('Notification', notificationSchema);

