-- Invitation template memory + the public `business-assets` bucket for
-- business profile pictures (logo/cover chosen outside the website media
-- library). Applied to the hosted project on 2026-09-26 before it was
-- checked in; recorded here verbatim so a fresh database matches it.
--
-- Writes are limited to the uploader's own folder (`<auth uid>/...`);
-- reads are public because these images are shown on public pages.

alter table public.business_invitations add column if not exists invited_template_id text;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('business-assets', 'business-assets', true, 10485760, array['image/jpeg','image/png','image/webp','image/gif'])
on conflict (id) do nothing;

drop policy if exists business_assets_public_read on storage.objects;
create policy business_assets_public_read on storage.objects for select using (bucket_id = 'business-assets');

drop policy if exists business_assets_insert on storage.objects;
create policy business_assets_insert on storage.objects for insert with check (
  bucket_id = 'business-assets' and (storage.foldername(name))[1] = (auth.uid())::text
);

drop policy if exists business_assets_update on storage.objects;
create policy business_assets_update on storage.objects for update using (
  bucket_id = 'business-assets' and (storage.foldername(name))[1] = (auth.uid())::text
);

drop policy if exists business_assets_delete on storage.objects;
create policy business_assets_delete on storage.objects for delete using (
  bucket_id = 'business-assets' and (storage.foldername(name))[1] = (auth.uid())::text
);
