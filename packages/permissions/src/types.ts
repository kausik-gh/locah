import { PermissionIdentifier } from './identifiers'

export interface PermissionGrant {
  id: string
  businessId: string
  membershipId: string
  permission: PermissionIdentifier
  locationIds: string[] | null // null = all locations
  grantedBy: string
  grantedAt: Date
}

export interface AppliedTemplate {
  id: string
  membershipId: string
  templateId: string
  appliedAt: Date
  appliedBy: string
  customized: boolean
}

export type PermissionTemplateId =
  | 'tmpl_store_manager'
  | 'tmpl_cashier'
  | 'tmpl_content_editor'
  | 'tmpl_inventory_manager'
  | 'tmpl_booking_coordinator'
  | 'tmpl_workforce_manager'
  | 'tmpl_lead_handler'

export interface PermissionTemplate {
  id: PermissionTemplateId
  name: string
  description: string
  permissions: PermissionIdentifier[]
}
