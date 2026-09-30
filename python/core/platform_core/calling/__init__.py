"""Calls: WhatsApp Business Calling and (later) phone lines, as one call record.

WhatsApp calling and ordinary phone calls are different channels with
different providers; they share only the call record (calls_sessions), the
audit, and the rule that a business never calls a customer who has not
allowed it.
"""
