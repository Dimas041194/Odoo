const mongoose = require('mongoose');

const matrixSchema = new mongoose.Schema({
  name: {
    type: String,
    required: true,
    trim: true,
    maxlength: 100
  },
  description: {
    type: String,
    trim: true,
    maxlength: 500
  },
  owner: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  collaborators: [{
    user: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User'
    },
    role: {
      type: String,
      enum: ['viewer', 'editor', 'admin'],
      default: 'viewer'
    },
    addedAt: {
      type: Date,
      default: Date.now
    }
  }],
  dimensions: {
    rows: {
      type: Number,
      required: true,
      min: 2,
      max: 1000
    },
    columns: {
      type: Number,
      required: true,
      min: 2,
      max: 1000
    }
  },
  data: {
    type: [[Number]],
    required: true
  },
  metadata: {
    version: {
      type: String,
      default: '1.0.0'
    },
    lastModified: {
      type: Date,
      default: Date.now
    },
    modificationCount: {
      type: Number,
      default: 0
    },
    tags: [{
      type: String,
      trim: true,
      maxlength: 30
    }],
    category: {
      type: String,
      enum: ['mathematics', 'statistics', 'data-analysis', 'machine-learning', 'simulation', 'other'],
      default: 'mathematics'
    }
  },
  settings: {
    isPublic: {
      type: Boolean,
      default: false
    },
    allowComments: {
      type: Boolean,
      default: true
    },
    allowExport: {
      type: Boolean,
      default: true
    },
    autoSave: {
      type: Boolean,
      default: true
    },
    gridVisible: {
      type: Boolean,
      default: true
    },
    cellSize: {
      type: Number,
      default: 40,
      min: 20,
      max: 100
    }
  },
  operations: [{
    type: {
      type: String,
      enum: ['add', 'subtract', 'multiply', 'divide', 'transpose', 'inverse', 'determinant', 'custom'],
      required: true
    },
    parameters: mongoose.Schema.Types.Mixed,
    result: mongoose.Schema.Types.Mixed,
    timestamp: {
      type: Date,
      default: Date.now
    },
    performedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User'
    }
  }],
  comments: [{
    user: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User'
    },
    content: {
      type: String,
      required: true,
      maxlength: 1000
    },
    position: {
      row: Number,
      column: Number
    },
    createdAt: {
      type: Date,
      default: Date.now
    },
    updatedAt: {
      type: Date,
      default: Date.now
    }
  }],
  isActive: {
    type: Boolean,
    default: true
  },
  createdAt: {
    type: Date,
    default: Date.now
  },
  updatedAt: {
    type: Date,
    default: Date.now
  }
}, {
  timestamps: true
});

// Indexes for better performance
matrixSchema.index({ owner: 1 });
matrixSchema.index({ 'collaborators.user': 1 });
matrixSchema.index({ 'metadata.tags': 1 });
matrixSchema.index({ 'metadata.category': 1 });
matrixSchema.index({ 'settings.isPublic': 1 });
matrixSchema.index({ createdAt: -1 });
matrixSchema.index({ 'metadata.lastModified': -1 });

// Update modification count and timestamp
matrixSchema.pre('save', function(next) {
  if (this.isModified('data')) {
    this.metadata.modificationCount += 1;
    this.metadata.lastModified = Date.now();
  }
  this.updatedAt = Date.now();
  next();
});

// Validate matrix dimensions match data
matrixSchema.pre('save', function(next) {
  if (this.data && this.data.length !== this.dimensions.rows) {
    return next(new Error('Matrix data rows do not match dimensions'));
  }
  if (this.data && this.data[0] && this.data[0].length !== this.dimensions.columns) {
    return next(new Error('Matrix data columns do not match dimensions'));
  }
  next();
});

// Virtual for matrix size
matrixSchema.virtual('size').get(function() {
  return this.dimensions.rows * this.dimensions.columns;
});

// Method to check if user has permission
matrixSchema.methods.hasPermission = function(userId, action) {
  // Owner has all permissions
  if (this.owner.toString() === userId.toString()) {
    return true;
  }
  
  // Check collaborator permissions
  const collaborator = this.collaborators.find(c => c.user.toString() === userId.toString());
  if (!collaborator) return false;
  
  switch (action) {
    case 'view':
      return ['viewer', 'editor', 'admin'].includes(collaborator.role);
    case 'edit':
      return ['editor', 'admin'].includes(collaborator.role);
    case 'admin':
      return collaborator.role === 'admin';
    default:
      return false;
  }
};

// Method to add collaborator
matrixSchema.methods.addCollaborator = function(userId, role = 'viewer') {
  const existingIndex = this.collaborators.findIndex(c => c.user.toString() === userId.toString());
  if (existingIndex >= 0) {
    this.collaborators[existingIndex].role = role;
  } else {
    this.collaborators.push({ user: userId, role });
  }
  return this.save();
};

// Method to remove collaborator
matrixSchema.methods.removeCollaborator = function(userId) {
  this.collaborators = this.collaborators.filter(c => c.user.toString() !== userId.toString());
  return this.save();
};

module.exports = mongoose.model('Matrix', matrixSchema);

