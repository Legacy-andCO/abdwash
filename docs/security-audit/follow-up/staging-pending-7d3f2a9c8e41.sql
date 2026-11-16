DO $$ BEGIN IF (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM '80826dfc3c2d' THEN RAISE EXCEPTION 'Unexpected Alembic predecessor'; END IF; END $$;
ALTER TABLE business_settings ADD COLUMN loyalty_enabled BOOLEAN DEFAULT true NOT NULL;
ALTER TABLE business_settings ADD COLUMN loyalty_required_washes INTEGER DEFAULT '9' NOT NULL;
ALTER TABLE business_settings ADD COLUMN loyalty_reward_service_id UUID;
ALTER TABLE business_settings ADD CONSTRAINT ck_business_settings_positive_loyalty_required_washes CHECK (loyalty_required_washes > 0);
ALTER TABLE business_settings ADD CONSTRAINT fk_business_settings_loyalty_reward_service FOREIGN KEY(loyalty_reward_service_id) REFERENCES services (id) ON DELETE SET NULL;
UPDATE business_settings AS settings
        SET loyalty_reward_service_id = candidate.service_id
        FROM (
            SELECT business_id, min(id::text)::uuid AS service_id
            FROM services
            WHERE is_active IS TRUE
            GROUP BY business_id
            HAVING count(*) = 1
        ) AS candidate
        WHERE settings.business_id = candidate.business_id
          AND settings.loyalty_reward_service_id IS NULL;
ALTER TABLE business_sync_revisions ADD COLUMN customers_revision BIGINT DEFAULT '0' NOT NULL;
CREATE TABLE loyalty_rewards (
	business_id UUID NOT NULL, 
	customer_profile_id UUID NOT NULL, 
	reward_service_id UUID NOT NULL, 
	reward_service_name VARCHAR(160) NOT NULL, 
	reward_list_price_minor INTEGER NOT NULL, 
	required_washes INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	reserved_booking_id UUID, 
	reserved_booking_service_id UUID, 
	redeemed_job_id UUID, 
	reserved_at TIMESTAMP WITH TIME ZONE, 
	redeemed_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_loyalty_rewards PRIMARY KEY (id), 
	CONSTRAINT ck_loyalty_rewards_loyalty_reward_status CHECK (status IN ('available','reserved','redeemed')), 
	CONSTRAINT ck_loyalty_rewards_nonnegative_reward_list_price CHECK (reward_list_price_minor >= 0), 
	CONSTRAINT ck_loyalty_rewards_positive_reward_required_washes CHECK (required_washes > 0), 
	CONSTRAINT fk_loyalty_rewards_business_id_businesses FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
	CONSTRAINT fk_loyalty_rewards_customer_profile_id_customer_profiles FOREIGN KEY(customer_profile_id) REFERENCES customer_profiles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_loyalty_rewards_reward_service_id_services FOREIGN KEY(reward_service_id) REFERENCES services (id), 
	CONSTRAINT fk_loyalty_rewards_reserved_booking_id_bookings FOREIGN KEY(reserved_booking_id) REFERENCES bookings (id), 
	CONSTRAINT fk_loyalty_rewards_reserved_booking_service_id_booking_services FOREIGN KEY(reserved_booking_service_id) REFERENCES booking_services (id), 
	CONSTRAINT fk_loyalty_rewards_redeemed_job_id_jobs FOREIGN KEY(redeemed_job_id) REFERENCES jobs (id), 
	CONSTRAINT uq_loyalty_rewards_reserved_booking_service_id UNIQUE (reserved_booking_service_id)
);
CREATE INDEX ix_loyalty_rewards_business_customer_status ON loyalty_rewards (business_id, customer_profile_id, status);
ALTER TABLE booking_services ADD COLUMN list_price_minor INTEGER;
UPDATE booking_services SET list_price_minor = unit_price_minor;
ALTER TABLE booking_services ALTER COLUMN list_price_minor SET NOT NULL;
ALTER TABLE booking_services ADD COLUMN discount_minor INTEGER DEFAULT '0' NOT NULL;
ALTER TABLE booking_services ADD COLUMN discount_type VARCHAR(30);
ALTER TABLE booking_services ADD COLUMN loyalty_reward_id UUID;
ALTER TABLE booking_services ADD CONSTRAINT ck_booking_services_nonnegative_booking_service_list_price CHECK (list_price_minor >= 0);
ALTER TABLE booking_services ADD CONSTRAINT ck_booking_services_nonnegative_booking_service_discount CHECK (discount_minor >= 0);
ALTER TABLE booking_services ADD CONSTRAINT ck_booking_services_booking_service_discount_within_list_price CHECK (discount_minor <= list_price_minor * quantity);
ALTER TABLE booking_services ADD CONSTRAINT ck_booking_services_booking_service_discount_type CHECK (discount_type IS NULL OR discount_type = 'loyalty_reward');
ALTER TABLE booking_services ADD CONSTRAINT fk_booking_services_loyalty_reward FOREIGN KEY(loyalty_reward_id) REFERENCES loyalty_rewards (id) ON DELETE SET NULL;
CREATE TABLE loyalty_events (
	business_id UUID NOT NULL, 
	customer_profile_id UUID NOT NULL, 
	event_type VARCHAR(30) NOT NULL, 
	quantity INTEGER NOT NULL, 
	job_id UUID, 
	booking_id UUID, 
	booking_vehicle_id UUID, 
	reward_id UUID, 
	actor_staff_id UUID, 
	reason TEXT, 
	source_key VARCHAR(200) NOT NULL, 
	id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_loyalty_events PRIMARY KEY (id), 
	CONSTRAINT ck_loyalty_events_loyalty_event_type CHECK (event_type IN ('qualifying_wash','manual_credit','manual_debit','reward_earned','reward_reserved','reward_released','reward_redeemed')), 
	CONSTRAINT ck_loyalty_events_loyalty_event_quantity CHECK ((event_type = 'manual_debit' AND quantity < 0) OR (event_type IN ('qualifying_wash','manual_credit') AND quantity > 0) OR (event_type LIKE 'reward_%' AND quantity = 0)), 
	CONSTRAINT fk_loyalty_events_business_id_businesses FOREIGN KEY(business_id) REFERENCES businesses (id) ON DELETE CASCADE, 
	CONSTRAINT fk_loyalty_events_customer_profile_id_customer_profiles FOREIGN KEY(customer_profile_id) REFERENCES customer_profiles (id) ON DELETE CASCADE, 
	CONSTRAINT fk_loyalty_events_job_id_jobs FOREIGN KEY(job_id) REFERENCES jobs (id), 
	CONSTRAINT fk_loyalty_events_booking_id_bookings FOREIGN KEY(booking_id) REFERENCES bookings (id), 
	CONSTRAINT fk_loyalty_events_booking_vehicle_id_booking_vehicles FOREIGN KEY(booking_vehicle_id) REFERENCES booking_vehicles (id), 
	CONSTRAINT fk_loyalty_events_reward_id_loyalty_rewards FOREIGN KEY(reward_id) REFERENCES loyalty_rewards (id), 
	CONSTRAINT fk_loyalty_events_actor_staff_id_staff_profiles FOREIGN KEY(actor_staff_id) REFERENCES staff_profiles (id), 
	CONSTRAINT uq_loyalty_event_source UNIQUE (business_id, source_key)
);
CREATE INDEX ix_loyalty_events_business_customer_created ON loyalty_events (business_id, customer_profile_id, created_at);
ALTER TABLE payment_transactions ADD COLUMN actor_staff_id UUID;
ALTER TABLE payment_transactions ADD COLUMN client_event_id VARCHAR(160);
ALTER TABLE payment_transactions ADD CONSTRAINT fk_payment_transactions_actor_staff FOREIGN KEY(actor_staff_id) REFERENCES staff_profiles (id);
ALTER TABLE payment_transactions ADD CONSTRAINT uq_payment_transaction_event UNIQUE (payment_id, client_event_id);
ALTER TABLE payment_transactions ADD COLUMN cash_tendered_minor INTEGER;
ALTER TABLE payment_transactions ADD COLUMN cash_change_minor INTEGER;
ALTER TABLE payment_transactions ADD CONSTRAINT ck_payment_transactions_cash_tender_fields_together CHECK ((cash_tendered_minor IS NULL AND cash_change_minor IS NULL) OR (cash_tendered_minor IS NOT NULL AND cash_change_minor IS NOT NULL));
ALTER TABLE payment_transactions ADD CONSTRAINT ck_payment_transactions_cash_tender_covers_payment CHECK (cash_tendered_minor IS NULL OR cash_tendered_minor >= amount_minor);
ALTER TABLE payment_transactions ADD CONSTRAINT ck_payment_transactions_nonnegative_cash_change CHECK (cash_change_minor IS NULL OR cash_change_minor >= 0);
ALTER TABLE payment_transactions ADD CONSTRAINT ck_payment_transactions_cash_change_matches_tender CHECK (cash_tendered_minor IS NULL OR cash_change_minor = cash_tendered_minor - amount_minor);
CREATE INDEX ix_customer_profiles_business_name_search ON customer_profiles (business_id, lower(first_name), lower(surname));
CREATE INDEX ix_vehicles_customer_plate_search ON vehicles (customer_id, lower(plate_number));
ALTER TABLE "loyalty_rewards" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "loyalty_events" ENABLE ROW LEVEL SECURITY;
UPDATE public.alembic_version SET version_num='7d3f2a9c8e41' WHERE version_num='80826dfc3c2d';
