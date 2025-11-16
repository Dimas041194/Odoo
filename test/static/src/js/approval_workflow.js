/* Approval Workflow JavaScript */

odoo.define('approval_workflow.ApprovalWorkflow', function (require) {
    'use strict';

    var core = require('web.core');
    var FormController = require('web.FormController');
    var ListController = require('web.ListController');
    var KanbanController = require('web.KanbanController');
    var Dialog = require('web.Dialog');
    var rpc = require('web.rpc');

    var _t = core._t;

    // Approval Workflow Form Controller
    FormController.include({
        events: _.extend({}, FormController.prototype.events, {
            'click .o_approval_approve_btn': '_onApproveClick',
            'click .o_approval_reject_btn': '_onRejectClick',
            'click .o_approval_cancel_btn': '_onCancelClick',
        }),

        _onApproveClick: function (ev) {
            ev.preventDefault();
            this._openApprovalDialog('approve');
        },

        _onRejectClick: function (ev) {
            ev.preventDefault();
            this._openApprovalDialog('reject');
        },

        _onCancelClick: function (ev) {
            ev.preventDefault();
            this._openApprovalDialog('cancel');
        },

        _openApprovalDialog: function (action_type) {
            var self = this;
            var title = action_type === 'approve' ? _t('Approve Workflow') : 
                       action_type === 'reject' ? _t('Reject Workflow') : 
                       _t('Cancel Workflow');
            
            var dialog = new Dialog(this, {
                title: title,
                size: 'medium',
                $content: $('<div>').append(
                    $('<div>').addClass('form-group').append(
                        $('<label>').text(_t('Comments (Optional)')),
                        $('<textarea>').addClass('form-control').attr('rows', 4).attr('name', 'comments')
                    )
                ),
                buttons: [
                    {
                        text: _t('Confirm'),
                        classes: 'btn-primary',
                        click: function () {
                            var comments = dialog.$content.find('textarea[name="comments"]').val();
                            self._performApprovalAction(action_type, comments);
                            dialog.close();
                        }
                    },
                    {
                        text: _t('Cancel'),
                        classes: 'btn-secondary',
                        click: function () {
                            dialog.close();
                        }
                    }
                ]
            });
            dialog.open();
        },

        _performApprovalAction: function (action_type, comments) {
            var self = this;
            var record_id = this.model.get(this.handle).get('id');
            
            rpc.query({
                model: 'approval.workflow',
                method: 'action_' + action_type,
                args: [record_id],
                kwargs: {
                    comments: comments || ''
                }
            }).then(function (result) {
                if (result) {
                    self.reload();
                    self.displayNotification({
                        title: _t('Success'),
                        message: _t('Workflow ' + action_type + 'd successfully'),
                        type: 'success'
                    });
                }
            }).catch(function (error) {
                self.displayNotification({
                    title: _t('Error'),
                    message: error.message || _t('An error occurred'),
                    type: 'danger'
                });
            });
        }
    });

    // Approval Workflow List Controller
    ListController.include({
        events: _.extend({}, ListController.prototype.events, {
            'click .o_approval_bulk_approve': '_onBulkApprove',
            'click .o_approval_bulk_reject': '_onBulkReject',
        }),

        _onBulkApprove: function (ev) {
            ev.preventDefault();
            this._performBulkAction('approve');
        },

        _onBulkReject: function (ev) {
            ev.preventDefault();
            this._performBulkAction('reject');
        },

        _performBulkAction: function (action_type) {
            var self = this;
            var selected_records = this.getSelectedRecords();
            
            if (selected_records.length === 0) {
                this.displayNotification({
                    title: _t('Warning'),
                    message: _t('Please select at least one record'),
                    type: 'warning'
                });
                return;
            }

            var dialog = new Dialog(this, {
                title: _t('Bulk ' + action_type.charAt(0).toUpperCase() + action_type.slice(1)),
                size: 'medium',
                $content: $('<div>').append(
                    $('<div>').addClass('form-group').append(
                        $('<label>').text(_t('Comments (Optional)')),
                        $('<textarea>').addClass('form-control').attr('rows', 4).attr('name', 'comments')
                    )
                ),
                buttons: [
                    {
                        text: _t('Confirm'),
                        classes: 'btn-primary',
                        click: function () {
                            var comments = dialog.$content.find('textarea[name="comments"]').val();
                            self._executeBulkAction(selected_records, action_type, comments);
                            dialog.close();
                        }
                    },
                    {
                        text: _t('Cancel'),
                        classes: 'btn-secondary',
                        click: function () {
                            dialog.close();
                        }
                    }
                ]
            });
            dialog.open();
        },

        _executeBulkAction: function (records, action_type, comments) {
            var self = this;
            var record_ids = records.map(function (record) {
                return record.id;
            });

            rpc.query({
                model: 'approval.workflow',
                method: 'action_' + action_type,
                args: [record_ids],
                kwargs: {
                    comments: comments || ''
                }
            }).then(function (result) {
                if (result) {
                    self.reload();
                    self.displayNotification({
                        title: _t('Success'),
                        message: _t('Bulk ' + action_type + ' completed successfully'),
                        type: 'success'
                    });
                }
            }).catch(function (error) {
                self.displayNotification({
                    title: _t('Error'),
                    message: error.message || _t('An error occurred'),
                    type: 'danger'
                });
            });
        }
    });

    // Approval Workflow Kanban Controller
    KanbanController.include({
        events: _.extend({}, KanbanController.prototype.events, {
            'click .o_approval_quick_approve': '_onQuickApprove',
            'click .o_approval_quick_reject': '_onQuickReject',
        }),

        _onQuickApprove: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var record_id = $(ev.currentTarget).data('record-id');
            this._performQuickAction(record_id, 'approve');
        },

        _onQuickReject: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var record_id = $(ev.currentTarget).data('record-id');
            this._performQuickAction(record_id, 'reject');
        },

        _performQuickAction: function (record_id, action_type) {
            var self = this;
            
            rpc.query({
                model: 'approval.workflow',
                method: 'action_' + action_type,
                args: [record_id],
                kwargs: {
                    comments: 'Quick ' + action_type
                }
            }).then(function (result) {
                if (result) {
                    self.reload();
                    self.displayNotification({
                        title: _t('Success'),
                        message: _t('Workflow ' + action_type + 'd successfully'),
                        type: 'success'
                    });
                }
            }).catch(function (error) {
                self.displayNotification({
                    title: _t('Error'),
                    message: error.message || _t('An error occurred'),
                    type: 'danger'
                });
            });
        }
    });

    // Approval Dashboard Widget
    var ApprovalDashboard = core.Class.extend({
        init: function (parent, options) {
            this.parent = parent;
            this.options = options || {};
        },

        start: function () {
            var self = this;
            this.$el = $('<div>').addClass('o_approval_dashboard');
            this._loadDashboardData();
            return this.$el;
        },

        _loadDashboardData: function () {
            var self = this;
            
            rpc.query({
                model: 'approval.workflow',
                method: 'get_dashboard_data'
            }).then(function (data) {
                self._renderDashboard(data);
            }).catch(function (error) {
                console.error('Error loading dashboard data:', error);
            });
        },

        _renderDashboard: function (data) {
            var self = this;
            var html = '<div class="o_approval_dashboard_stats">';
            
            // Statistics Cards
            html += '<div class="o_approval_stat_card">';
            html += '<div class="o_approval_stat_number">' + data.my_workflows.total + '</div>';
            html += '<div class="o_approval_stat_label">Total Workflows</div>';
            html += '</div>';
            
            html += '<div class="o_approval_stat_card">';
            html += '<div class="o_approval_stat_number">' + data.my_workflows.pending + '</div>';
            html += '<div class="o_approval_stat_label">Pending</div>';
            html += '</div>';
            
            html += '<div class="o_approval_stat_card">';
            html += '<div class="o_approval_stat_number">' + data.my_workflows.approved + '</div>';
            html += '<div class="o_approval_stat_label">Approved</div>';
            html += '</div>';
            
            html += '<div class="o_approval_stat_card">';
            html += '<div class="o_approval_stat_number">' + data.pending_approvals.total + '</div>';
            html += '<div class="o_approval_stat_label">Pending My Approval</div>';
            html += '</div>';
            
            html += '</div>';
            
            // Recent Activities
            html += '<div class="o_approval_dashboard_charts">';
            html += '<div class="o_approval_chart_card">';
            html += '<div class="o_approval_chart_title">Recent Activities</div>';
            html += '<div class="o_approval_recent_activities">';
            
            data.recent_activities.forEach(function (activity) {
                html += '<div class="o_approval_card">';
                html += '<div class="o_approval_card_header">';
                html += '<div class="o_approval_card_title">' + activity.name + '</div>';
                html += '<div class="o_approval_card_status o_approval_status_' + activity.state + '">' + activity.state + '</div>';
                html += '</div>';
                html += '<div class="o_approval_card_body">';
                html += 'Amount: ' + activity.amount + ' ' + activity.currency;
                html += '</div>';
                html += '<div class="o_approval_card_footer">';
                html += '<small>' + activity.last_update + '</small>';
                html += '</div>';
                html += '</div>';
            });
            
            html += '</div>';
            html += '</div>';
            html += '</div>';
            
            this.$el.html(html);
        }
    });

    return {
        ApprovalDashboard: ApprovalDashboard
    };
});
