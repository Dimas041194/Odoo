const express = require('express');
const { body, validationResult, query } = require('express-validator');
const Matrix = require('../models/Matrix');
const User = require('../models/User');
const { requireRole, requirePermission } = require('../middleware/auth');
const { notifyMatrixCreated, notifyMatrixUpdated, notifyMatrixShared, notifyCollaboratorAdded } = require('../services/notificationService');

const router = express.Router();

// Get all matrices for user
router.get('/', [
  query('page').optional().isInt({ min: 1 }),
  query('limit').optional().isInt({ min: 1, max: 100 }),
  query('search').optional().isLength({ min: 1, max: 100 }),
  query('category').optional().isIn(['mathematics', 'statistics', 'data-analysis', 'machine-learning', 'simulation', 'other']),
  query('sortBy').optional().isIn(['name', 'createdAt', 'updatedAt', 'size']),
  query('sortOrder').optional().isIn(['asc', 'desc'])
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        message: 'Validation failed',
        errors: errors.array()
      });
    }

    const {
      page = 1,
      limit = 20,
      search,
      category,
      sortBy = 'updatedAt',
      sortOrder = 'desc'
    } = req.query;

    // Build query
    const query = {
      $or: [
        { owner: req.user._id },
        { 'collaborators.user': req.user._id }
      ],
      isActive: true
    };

    if (search) {
      query.$and = [
        {
          $or: [
            { name: { $regex: search, $options: 'i' } },
            { description: { $regex: search, $options: 'i' } },
            { 'metadata.tags': { $regex: search, $options: 'i' } }
          ]
        }
      ];
    }

    if (category) {
      query['metadata.category'] = category;
    }

    // Build sort object
    const sort = {};
    sort[sortBy] = sortOrder === 'asc' ? 1 : -1;

    const matrices = await Matrix.find(query)
      .populate('owner', 'username firstName lastName avatar')
      .populate('collaborators.user', 'username firstName lastName avatar')
      .sort(sort)
      .skip((page - 1) * limit)
      .limit(parseInt(limit));

    const total = await Matrix.countDocuments(query);

    res.json({
      matrices,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total,
        pages: Math.ceil(total / limit)
      }
    });
  } catch (error) {
    console.error('Get matrices error:', error);
    res.status(500).json({ message: 'Failed to get matrices' });
  }
});

// Get single matrix
router.get('/:id', async (req, res) => {
  try {
    const matrix = await Matrix.findById(req.params.id)
      .populate('owner', 'username firstName lastName avatar')
      .populate('collaborators.user', 'username firstName lastName avatar')
      .populate('comments.user', 'username firstName lastName avatar');

    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions
    if (!matrix.hasPermission(req.user._id, 'view')) {
      return res.status(403).json({ message: 'Access denied' });
    }

    res.json({ matrix });
  } catch (error) {
    console.error('Get matrix error:', error);
    res.status(500).json({ message: 'Failed to get matrix' });
  }
});

// Create new matrix
router.post('/', [
  body('name').isLength({ min: 1, max: 100 }).withMessage('Matrix name is required'),
  body('description').optional().isLength({ max: 500 }),
  body('dimensions.rows').isInt({ min: 2, max: 1000 }).withMessage('Rows must be between 2 and 1000'),
  body('dimensions.columns').isInt({ min: 2, max: 1000 }).withMessage('Columns must be between 2 and 1000'),
  body('data').isArray().withMessage('Matrix data is required'),
  body('metadata.category').optional().isIn(['mathematics', 'statistics', 'data-analysis', 'machine-learning', 'simulation', 'other']),
  body('settings.isPublic').optional().isBoolean()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        message: 'Validation failed',
        errors: errors.array()
      });
    }

    const { name, description, dimensions, data, metadata = {}, settings = {} } = req.body;

    // Validate data dimensions
    if (data.length !== dimensions.rows) {
      return res.status(400).json({ message: 'Data rows do not match dimensions' });
    }
    if (data[0] && data[0].length !== dimensions.columns) {
      return res.status(400).json({ message: 'Data columns do not match dimensions' });
    }

    // Create matrix
    const matrix = new Matrix({
      name,
      description,
      owner: req.user._id,
      dimensions,
      data,
      metadata: {
        ...metadata,
        category: metadata.category || 'mathematics'
      },
      settings: {
        isPublic: settings.isPublic || false,
        allowComments: settings.allowComments !== false,
        allowExport: settings.allowExport !== false,
        autoSave: settings.autoSave !== false,
        gridVisible: settings.gridVisible !== false,
        cellSize: settings.cellSize || 40
      }
    });

    await matrix.save();

    // Populate owner info
    await matrix.populate('owner', 'username firstName lastName avatar');

    // Send notification
    await notifyMatrixCreated(matrix, req.user);

    res.status(201).json({
      message: 'Matrix created successfully',
      matrix
    });
  } catch (error) {
    console.error('Create matrix error:', error);
    res.status(500).json({ message: 'Failed to create matrix' });
  }
});

// Update matrix
router.put('/:id', [
  body('name').optional().isLength({ min: 1, max: 100 }),
  body('description').optional().isLength({ max: 500 }),
  body('data').optional().isArray(),
  body('settings').optional().isObject()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        message: 'Validation failed',
        errors: errors.array()
      });
    }

    const matrix = await Matrix.findById(req.params.id);
    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions
    if (!matrix.hasPermission(req.user._id, 'edit')) {
      return res.status(403).json({ message: 'Access denied' });
    }

    const { name, description, data, settings } = req.body;
    const updates = {};

    if (name !== undefined) updates.name = name;
    if (description !== undefined) updates.description = description;
    if (settings !== undefined) updates.settings = { ...matrix.settings, ...settings };

    if (data !== undefined) {
      // Validate data dimensions
      if (data.length !== matrix.dimensions.rows) {
        return res.status(400).json({ message: 'Data rows do not match dimensions' });
      }
      if (data[0] && data[0].length !== matrix.dimensions.columns) {
        return res.status(400).json({ message: 'Data columns do not match dimensions' });
      }
      updates.data = data;
    }

    const updatedMatrix = await Matrix.findByIdAndUpdate(
      req.params.id,
      updates,
      { new: true, runValidators: true }
    )
    .populate('owner', 'username firstName lastName avatar')
    .populate('collaborators.user', 'username firstName lastName avatar');

    // Notify collaborators
    const collaborators = updatedMatrix.collaborators.map(c => c.user);
    if (collaborators.length > 0) {
      await notifyMatrixUpdated(updatedMatrix, req.user, collaborators);
    }

    res.json({
      message: 'Matrix updated successfully',
      matrix: updatedMatrix
    });
  } catch (error) {
    console.error('Update matrix error:', error);
    res.status(500).json({ message: 'Failed to update matrix' });
  }
});

// Delete matrix
router.delete('/:id', async (req, res) => {
  try {
    const matrix = await Matrix.findById(req.params.id);
    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions (only owner can delete)
    if (matrix.owner.toString() !== req.user._id.toString()) {
      return res.status(403).json({ message: 'Only the owner can delete this matrix' });
    }

    matrix.isActive = false;
    await matrix.save();

    res.json({ message: 'Matrix deleted successfully' });
  } catch (error) {
    console.error('Delete matrix error:', error);
    res.status(500).json({ message: 'Failed to delete matrix' });
  }
});

// Add collaborator
router.post('/:id/collaborators', [
  body('email').isEmail().withMessage('Valid email is required'),
  body('role').isIn(['viewer', 'editor', 'admin']).withMessage('Valid role is required')
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        message: 'Validation failed',
        errors: errors.array()
      });
    }

    const { email, role } = req.body;
    const matrix = await Matrix.findById(req.params.id);
    
    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions
    if (!matrix.hasPermission(req.user._id, 'admin')) {
      return res.status(403).json({ message: 'Access denied' });
    }

    // Find user by email
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    // Check if already a collaborator
    const existingCollaborator = matrix.collaborators.find(
      c => c.user.toString() === user._id.toString()
    );

    if (existingCollaborator) {
      return res.status(400).json({ message: 'User is already a collaborator' });
    }

    // Add collaborator
    await matrix.addCollaborator(user._id, role);

    // Send notification
    await notifyCollaboratorAdded(matrix, user, req.user);

    // Send email notification
    try {
      const { sendEmail } = require('../services/emailService');
      await sendEmail({
        to: user.email,
        subject: 'Matrix Shared with You',
        template: 'matrixShared',
        data: {
          recipientName: user.fullName,
          sharerName: req.user.fullName,
          matrixName: matrix.name,
          matrixSize: `${matrix.dimensions.rows}x${matrix.dimensions.columns}`,
          role: role,
          description: matrix.description,
          matrixLink: `${process.env.CLIENT_URL}/matrices/${matrix._id}`
        }
      });
    } catch (emailError) {
      console.error('Failed to send email notification:', emailError);
    }

    res.json({ message: 'Collaborator added successfully' });
  } catch (error) {
    console.error('Add collaborator error:', error);
    res.status(500).json({ message: 'Failed to add collaborator' });
  }
});

// Remove collaborator
router.delete('/:id/collaborators/:userId', async (req, res) => {
  try {
    const matrix = await Matrix.findById(req.params.id);
    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions
    if (!matrix.hasPermission(req.user._id, 'admin')) {
      return res.status(403).json({ message: 'Access denied' });
    }

    await matrix.removeCollaborator(req.params.userId);

    res.json({ message: 'Collaborator removed successfully' });
  } catch (error) {
    console.error('Remove collaborator error:', error);
    res.status(500).json({ message: 'Failed to remove collaborator' });
  }
});

// Perform matrix operation
router.post('/:id/operations', [
  body('type').isIn(['add', 'subtract', 'multiply', 'divide', 'transpose', 'inverse', 'determinant']).withMessage('Valid operation type is required'),
  body('parameters').optional().isObject()
], async (req, res) => {
  try {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ 
        message: 'Validation failed',
        errors: errors.array()
      });
    }

    const matrix = await Matrix.findById(req.params.id);
    if (!matrix) {
      return res.status(404).json({ message: 'Matrix not found' });
    }

    // Check permissions
    if (!matrix.hasPermission(req.user._id, 'edit')) {
      return res.status(403).json({ message: 'Access denied' });
    }

    const { type, parameters = {} } = req.body;
    let result;

    // Perform operation based on type
    switch (type) {
      case 'transpose':
        result = transposeMatrix(matrix.data);
        break;
      case 'determinant':
        if (matrix.dimensions.rows !== matrix.dimensions.columns) {
          return res.status(400).json({ message: 'Determinant can only be calculated for square matrices' });
        }
        result = calculateDeterminant(matrix.data);
        break;
      case 'add':
      case 'subtract':
      case 'multiply':
      case 'divide':
        if (!parameters.matrix) {
          return res.status(400).json({ message: 'Second matrix is required for this operation' });
        }
        result = performMatrixOperation(matrix.data, parameters.matrix, type);
        break;
      default:
        return res.status(400).json({ message: 'Unsupported operation' });
    }

    // Add operation to history
    matrix.operations.push({
      type,
      parameters,
      result,
      performedBy: req.user._id
    });

    await matrix.save();

    res.json({
      message: 'Operation completed successfully',
      result,
      operation: {
        type,
        parameters,
        result,
        timestamp: new Date()
      }
    });
  } catch (error) {
    console.error('Matrix operation error:', error);
    res.status(500).json({ message: 'Operation failed' });
  }
});

// Matrix operation helper functions
function transposeMatrix(matrix) {
  return matrix[0].map((_, colIndex) => matrix.map(row => row[colIndex]));
}

function calculateDeterminant(matrix) {
  const n = matrix.length;
  if (n === 1) return matrix[0][0];
  if (n === 2) return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0];
  
  let det = 0;
  for (let i = 0; i < n; i++) {
    const subMatrix = matrix.slice(1).map(row => row.filter((_, colIndex) => colIndex !== i));
    det += Math.pow(-1, i) * matrix[0][i] * calculateDeterminant(subMatrix);
  }
  return det;
}

function performMatrixOperation(matrix1, matrix2, operation) {
  const rows1 = matrix1.length;
  const cols1 = matrix1[0].length;
  const rows2 = matrix2.length;
  const cols2 = matrix2[0].length;

  switch (operation) {
    case 'add':
    case 'subtract':
      if (rows1 !== rows2 || cols1 !== cols2) {
        throw new Error('Matrices must have the same dimensions for addition/subtraction');
      }
      return matrix1.map((row, i) => 
        row.map((val, j) => 
          operation === 'add' ? val + matrix2[i][j] : val - matrix2[i][j]
        )
      );
    
    case 'multiply':
      if (cols1 !== rows2) {
        throw new Error('Number of columns in first matrix must equal number of rows in second matrix');
      }
      const result = Array(rows1).fill().map(() => Array(cols2).fill(0));
      for (let i = 0; i < rows1; i++) {
        for (let j = 0; j < cols2; j++) {
          for (let k = 0; k < cols1; k++) {
            result[i][j] += matrix1[i][k] * matrix2[k][j];
          }
        }
      }
      return result;
    
    case 'divide':
      // Matrix division is multiplication by inverse
      const inverse = calculateMatrixInverse(matrix2);
      return performMatrixOperation(matrix1, inverse, 'multiply');
    
    default:
      throw new Error('Unsupported operation');
  }
}

function calculateMatrixInverse(matrix) {
  const n = matrix.length;
  if (n !== matrix[0].length) {
    throw new Error('Matrix must be square to calculate inverse');
  }
  
  const det = calculateDeterminant(matrix);
  if (Math.abs(det) < 1e-10) {
    throw new Error('Matrix is singular and cannot be inverted');
  }
  
  // For simplicity, implementing 2x2 inverse
  if (n === 2) {
    const [[a, b], [c, d]] = matrix;
    return [
      [d / det, -b / det],
      [-c / det, a / det]
    ];
  }
  
  // For larger matrices, would need more complex implementation
  throw new Error('Inverse calculation for matrices larger than 2x2 not implemented');
}

module.exports = router;


