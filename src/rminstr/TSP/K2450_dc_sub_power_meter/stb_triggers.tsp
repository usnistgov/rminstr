
-- Trigger Models that Flip Operation Status Bytes sending Log Events-- 
function OSBbit0_low()
	trigger.model.load("Empty")
	trigger.model.setblock(1, trigger.BLOCK_LOG_EVENT, trigger.LOG_INFO2, "Set OSB Bit Low.")
	trigger.model.initiate()

end

-- Status Bit should be set high at begining of feedback loop
function OSBbit0_high()
	trigger.model.load("Empty")
	trigger.model.setblock(1, trigger.BLOCK_LOG_EVENT, trigger.LOG_INFO1, "Set OSB Bit 0 High.")
	trigger.model.initiate()

end


function wait_until_trigger()

	trigger.model.load("Empty")
	trigger.model.setblock(1, trigger.BLOCK_WAIT, trigger.EVENT_DISPLAY)
	trigger.model.setblock(2, trigger.BLOCK_LOG_EVENT, trigger.LOG_INFO1, "Set OSB Bit 0 High.")
	trigger.model.initiate()
end

