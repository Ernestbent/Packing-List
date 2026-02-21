# import frappe
# from frappe import _
# import json

# # ========================================
# # ROOM MANAGEMENT
# # ========================================

# @frappe.whitelist()
# def join_packing_list_room(packing_list):
#     """Join real-time room for a specific packing list"""
#     try:
#         # Publish to the specific room
#         frappe.publish_realtime(
#             event='join_packing_list_room',
#             message={
#                 'packing_list': packing_list,
#                 'user': frappe.session.user,
#                 'success': True
#             },
#             room=packing_list,
#             after_commit=True  # Important: ensures the room is joined after DB commit
#         )
#         return {'success': True}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Join Room Error')
#         return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def leave_packing_list_room(packing_list):
#     """Leave real-time room for a specific packing list"""
#     try:
#         frappe.publish_realtime(
#             event='leave_packing_list_room',
#             message={
#                 'packing_list': packing_list,
#                 'user': frappe.session.user,
#                 'success': True
#             },
#             room=packing_list,
#             after_commit=True
#         )
#         return {'success': True}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Leave Room Error')
#         return {'success': False, 'error': str(e)}

# # ========================================
# # EXISTING METHODS (IMPROVED)
# # ========================================

# @frappe.whitelist()
# def update_packaging_row(packing_list, row_name, fieldname, value):
#     """
#     Update a single field in a Packaging Details row and broadcast to all users
#     """
#     try:
#         doc = frappe.get_doc('Packing List', packing_list)
#         row = next((r for r in doc.table_hqkk if r.name == row_name), None)
#         if not row:
#             frappe.throw(_("Row not found"))

#         if fieldname in ['verifier_1', 'verifier_2']:
#             value = 1 if value else 0

#         row.set(fieldname, value)
#         doc.save(ignore_permissions=True)
#         frappe.db.commit()

#         # IMPORTANT: Use after_commit=True to ensure the event is sent after DB commit
#         frappe.publish_realtime(
#             event='packing_list_row_updated',
#             message={
#                 'packing_list': packing_list,
#                 'row_name': row_name,
#                 'fieldname': fieldname,
#                 'value': value,
#                 'updated_by': frappe.session.user,
#                 'timestamp': frappe.utils.now()
#             },
#             room=packing_list,
#             after_commit=True  # Add this!
#         )
        
#         frappe.response['message'] = {'success': True}
#         return {'success': True}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Real-time Update Error')
#         return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def add_packaging_rows(packing_list, box_number, items_json, box_weight):
#     """
#     Add multiple rows for one box + update box weight + broadcast
#     """
#     try:
#         items = json.loads(items_json)
#         doc = frappe.get_doc('Packing List', packing_list)

#         added_rows = []
#         for it in items:
#             row = doc.append('table_hqkk', {
#                 'box_number': int(box_number),
#                 'item': it['item'],
#                 'quantity': float(it['quantity']),
#                 'uom': it.get('uom')
#             })
#             added_rows.append({
#                 'name': row.name,
#                 'box_number': row.box_number,
#                 'item': row.item,
#                 'quantity': row.quantity,
#                 'uom': row.uom,
#                 'verifier_1': row.get('verifier_1', 0),
#                 'verifier_2': row.get('verifier_2', 0),
#                 'idx': row.idx
#             })

#         # Update or create box summary
#         box_row = next((b for b in doc.custom_box_summary if b.box_number == int(box_number)), None)
#         if box_row:
#             box_row.weight_kg = float(box_weight)
#         else:
#             doc.append('custom_box_summary', {
#                 'box_number': int(box_number),
#                 'weight_kg': float(box_weight)
#             })

#         doc.save(ignore_permissions=True)
#         frappe.db.commit()

#         # IMPORTANT: Use after_commit=True
#         frappe.publish_realtime(
#             event='packing_list_rows_added_multi',
#             message={
#                 'packing_list': packing_list,
#                 'box_number': int(box_number),
#                 'rows': added_rows,
#                 'box_weight': float(box_weight),
#                 'added_by': frappe.session.user,
#                 'timestamp': frappe.utils.now()
#             },
#             room=packing_list,
#             after_commit=True  # Add this!
#         )
        
#         return {'success': True, 'row_names': [r['name'] for r in added_rows]}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Add Rows Error')
#         return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def delete_packaging_rows(packing_list, row_names):
#     """
#     Delete multiple rows and broadcast
#     """
#     try:
#         if isinstance(row_names, str):
#             row_names = json.loads(row_names)

#         doc = frappe.get_doc('Packing List', packing_list)
        
#         # Store deleted row info for the message
#         deleted_rows = [r for r in doc.table_hqkk if r.name in row_names]
#         deleted_box_numbers = list(set([r.box_number for r in deleted_rows if r.box_number]))
        
#         # Remove the rows
#         doc.table_hqkk = [r for r in doc.table_hqkk if r.name not in row_names]
#         doc.save(ignore_permissions=True)
#         frappe.db.commit()

#         # IMPORTANT: Use after_commit=True
#         frappe.publish_realtime(
#             event='packing_list_rows_deleted',
#             message={
#                 'packing_list': packing_list,
#                 'row_names': row_names,
#                 'deleted_by': frappe.session.user,
#                 'box_numbers': deleted_box_numbers,
#                 'timestamp': frappe.utils.now()
#             },
#             room=packing_list,
#             after_commit=True  # Add this!
#         )
        
#         return {'success': True}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Delete Rows Error')
#         return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def update_box_weight(packing_list, box_number, weight):
#     """
#     Update or create box weight in custom_box_summary and broadcast
#     """
#     try:
#         doc = frappe.get_doc('Packing List', packing_list)
#         box_row = next((b for b in doc.custom_box_summary if b.box_number == int(box_number)), None)
#         if box_row:
#             box_row.weight_kg = float(weight)
#         else:
#             doc.append('custom_box_summary', {
#                 'box_number': int(box_number),
#                 'weight_kg': float(weight)
#             })

#         doc.save(ignore_permissions=True)
#         frappe.db.commit()

#         # IMPORTANT: Use after_commit=True
#         frappe.publish_realtime(
#             event='packing_list_box_weight_updated',
#             message={
#                 'packing_list': packing_list,
#                 'box_number': int(box_number),
#                 'weight': float(weight),
#                 'updated_by': frappe.session.user,
#                 'timestamp': frappe.utils.now()
#             },
#             room=packing_list,
#             after_commit=True  # Add this!
#         )
        
#         return {'success': True}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Box Weight Update Error')
#         return {'success': False, 'error': str(e)}

# # ========================================
# # DEBUGGING/HELPER METHODS
# # ========================================

# @frappe.whitelist()
# def test_realtime(packing_list):
#     """Test real-time communication"""
#     try:
#         frappe.publish_realtime(
#             event='test_event',
#             message={
#                 'packing_list': packing_list,
#                 'test': 'This is a test message',
#                 'user': frappe.session.user,
#                 'time': frappe.utils.now()
#             },
#             room=packing_list,
#             after_commit=True
#         )
#         return {'success': True, 'message': 'Test event published'}
#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), 'Packing List Test Error')
#         return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def get_room_status(packing_list):
#     """Check if room exists and get active users (debugging)"""
#     try:
#         # This is a debugging method - you can't actually get active users list
#         # But it helps verify the document exists
#         doc = frappe.get_doc('Packing List', packing_list)
#         return {
#             'success': True,
#             'packing_list': packing_list,
#             'exists': True,
#             'message': f'Room {packing_list} is active'
#         }
#     except Exception as e:
#         return {
#             'success': False,
#             'error': str(e)
#         }