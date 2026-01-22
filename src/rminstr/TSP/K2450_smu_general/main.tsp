-- SMU Source Sweep Script

--TODO Please insert code here.
----------------------------------------------------
display.settext(display.TEXT2,"K2450_smu_general")
----------------------------------------------------

----------------------------------------------------
-- Define voltage config list
----------------------------------------------------

smu.source.configlist.create("source_config_list")
for index = 1, table.getn(source_levels) do
 	smu.source.level = source_levels[index]
 	smu.source.configlist.store("source_config_list")
end
smu.source.level = source_levels[1]

----------------------------------------------------
-- Buffer Settings
----------------------------------------------------
if bf == nil then 
	bf = buffer.make(buffer_size, buffer.STYLE_STANDARD);
	bf.fillmode = buffer_fill_mode;
end
bf.clear()

----------------------------------------------------
-- Trigger model Definition
----------------------------------------------------
-- Duration Loop Trigger Model
if measure_for_duration_or_count == 'duration' then
	display.settext(display.TEXT2,"Armed:Duration Sweep")
	trigger.model.load("Empty")
	trigger.model.setblock(1, trigger.BLOCK_LOG_EVENT, trigger.LOG_INFO1, "Set OSB Bit 0 High.")
	trigger.model.setblock(2, trigger.BLOCK_BUFFER_CLEAR, bf) -- clear buffer
	trigger.model.setblock(3, trigger.BLOCK_CONFIG_RECALL,"source_config_list", 1) --starta at index 1 of sweep list
	trigger.model.setblock(4, trigger.BLOCK_SOURCE_OUTPUT, smu.ON)  --turn on source
	trigger.model.setblock(5, trigger.BLOCK_MEASURE_DIGITIZE,bf,trigger.COUNT_INFINITE) -- start measuring
	-- first measurement can have the time adjusted. Future versions should support list iteration, not sure how to do that at the moment.
	if initial_level_duration == nil then
		trigger.model.setblock(6, trigger.BLOCK_DELAY_CONSTANT, duration_per_level)
	else
		trigger.model.setblock(6, trigger.BLOCK_DELAY_CONSTANT, initial_level_duration)
	end
	
	-- stop the first measurement
	trigger.model.setblock(7, trigger.BLOCK_MEASURE_DIGITIZE,bf,trigger.COUNT_STOP)
	--trigger.model.setblock(8, trigger.BLOCK_BRANCH_COUNTER,table.getn(source_levels),8)
	
	--This line fataly crashes the SMU sometimes, use with caution -Zenn
	--trigger.model.setblock(7, trigger.BLOCK_BRANCH_ALWAYS, 11) --skip to timer stop in loop
	
	--loop starts here
	-- if there is more then 1 measurement value, iterate through
	if table.getn(source_levels) > 1 then
    	trigger.model.setblock(8, trigger.BLOCK_CONFIG_NEXT, "source_config_list") -- next voltage
    	trigger.model.setblock(9, trigger.BLOCK_MEASURE_DIGITIZE,bf,trigger.COUNT_INFINITE) -- start measuring
    	trigger.model.setblock(10, trigger.BLOCK_DELAY_CONSTANT, duration_per_level)
    	trigger.model.setblock(11, trigger.BLOCK_MEASURE_DIGITIZE,bf,trigger.COUNT_STOP)--Armed
    	trigger.model.setblock(12, trigger.BLOCK_BRANCH_COUNTER,table.getn(source_levels)-1,8)
	end

-- Number of Readings Trigger Model
elseif  measure_for_duration_or_count == 'count' then
	display.settext(display.TEXT2,"Armed:Count Sweep")
	trigger.model.load("Empty")
	trigger.model.setblock(1, trigger.BLOCK_LOG_EVENT, trigger.LOG_INFO1, "Set OSB Bit 0 High.")
	trigger.model.setblock(2, trigger.BLOCK_BUFFER_CLEAR, bf) -- clear buffer
	
	--If we are looping the SMU output = on block, we only need to call config next in the loop so we don't need this -Zenn
	--trigger.model.setblock(2, trigger.BLOCK_CONFIG_RECALL,"source_config_list", 1) --start at index 1 of sweep list
	
	--This line fataly crashes the SMU sometimes, use with caution -Zenn
	--trigger.model.setblock(2, trigger.BLOCK_BRANCH_ALWAYS, 4) --skip to timer start in loop
	
	--loop starts here
	trigger.model.setblock(3, trigger.BLOCK_CONFIG_NEXT, "source_config_list") -- next voltage
	trigger.model.setblock(4, trigger.BLOCK_SOURCE_OUTPUT, smu.ON)  --turn on source
	trigger.model.setblock(5, trigger.BLOCK_MEASURE_DIGITIZE,bf,count_per_level) -- start measuring
	trigger.model.setblock(6, trigger.BLOCK_BRANCH_COUNTER,table.getn(source_levels),3)
end
----------------------------------------------------
-- Arming/Triggering
----------------------------------------------------
-- Wait to Trigger Trigger Model

if trigger_mode == "bus" or trigger_mode == "BUS" then
	trigger.clear()
	triggered = trigger.wait(trigger_timeout)
else
	eventlog.post("trigger_mode not recognized. Defaulting to bus")
	trigger.clear()
	triggered = trigger.wait(trigger_timeout)
end

if smu.measure.autozero.enable == smu.OFF then
	smu.measure.autozero.once() 
end

display.settext(display.TEXT2,"Measuring")
trigger.model.initiate()
waitcomplete()

----------------------------------------------------
-- Termination
----------------------------------------------------
smu.source.configlist.delete("source_config_list")
display.settext(display.TEXT2,"idle")
print(termination_str)
