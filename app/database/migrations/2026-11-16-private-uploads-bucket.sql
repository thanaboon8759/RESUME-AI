-- For projects created before 2026-11-16: run once in the Supabase SQL Editor. Safe to run again.
UPDATE storage.buckets SET public = false, file_size_limit = 20971520 WHERE id = 'uploads';
