from odoo import http
from odoo.http import request

class ApprovalController(http.Controller):

    @http.route(['/approve/<model("x.new.approval.request"):approval_request>/<string:action>/<string:token>'], type='http', auth='public', website=False)
    def approve_request(self, approval_request=None, action=None, token=None, **kwargs):
        if not approval_request or not token:
            return request.not_found()
        try:
            if action == 'approve':
                approval_request.action_approve(token=token)
            elif action == 'reject':
                approval_request.action_reject(token=token)
            else:
                return request.not_found()
            return request.redirect('/web#id=%s&model=%s&view_type=form' % (approval_request.id, 'x.new.approval.request'))
        except Exception as e:
            return request.render('new_approval.approval_error', {'error': str(e)})
