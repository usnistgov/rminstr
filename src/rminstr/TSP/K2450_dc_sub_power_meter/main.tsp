--K2450 DC Substituted Power Meter Main Script

--TODO--------------------------------------------------
-- add external triggers


----------------------------------------------------
-- Pre Armed Routines
----------------------------------------------------

display.settext(display.TEXT1,"DC SUB")
display.settext(display.TEXT2,"Armed")
smu.source.output = smu.ON
status.clear()
--status.operation.setmap(0, trigger.LOG_INFO1, trigger.LOG_INFO2)
status.operation.enable = 1
status.request_enable = status.OSB
status.request_enable = status.OSB

eventlog.clear()

--Make buffer it not defined, otherwise just clear it
if bf == nil then 
	bf = buffer.make(buffer_size, buffer.STYLE_STANDARD);
	bf.fillmode = buffer_fill_mode;
end
bf.clear()

-------------------
---- Arming Methods 
-------------------
-- autozero here if autozeroing is off
-- Should make measurements more accurate
if smu.measure.autozero.enable == smu.OFF then
	smu.measure.autozero.once() 
end
waitcomplete()

-- Trigger detection
trigger.clear()
-- set trigger in line
digio.line[1].reset()
digio.line[1].mode =  digio.MODE_TRIGGER_IN
trigger.digin[1].edge = trigger.EDGE_EITHER
-- set trigger out line
digio.line[5].reset()
digio.line[5].mode = digio.MODE_TRIGGER_OUT


-- not sure if this is a good/bad pulse width.
if trigger_source == "bus" then
	triggered = trigger.wait(trigger_timeout)
elseif trigger_source == "ext" then
 	triggered = trigger.digin[1].wait(trigger_timeout)
else
	eventlog.post("trigger_mode not recognized. Defaulting to bus")
	triggered = trigger.wait(trigger_timeout)
end
-- Sets the status bit high to signal in the loop
-- define trigger model to set OSB
trigger.model.load("Empty")
trigger.model.setblock(1, trigger.BLOCK_BUFFER_CLEAR, defbuffer1)
status.operation.setmap(0, 2731, 2732)
trigger.model.initiate()
--OSBbit0_high()

-- Force Script to wait until trigger models complete to enter feedback loop
-- waitcomplete()

-------------------------
--Post Trigger, Pre Measurement Routine
-------------------------


-- Send any output triggers
if trigger_out then trigger.digout[5].assert() end
	
-- Delay start of feedback loop
delay(trigger_delay)
local i = 1
local time = 0
local t0 = 0
----------------------------------------------
--Controlling Routines (Sensor Type Dependent)
----------------------------------------------
local last_triggered = true

--Platinum Thin Film Sensor Routine
----------------------------------------------
if sensor_type == 'platinum_thinfilm' then 
	display.settext(display.TEXT1,"DC SUB - Thinfilm")
	while (time < duration)
	do
		-- get measurements
		smu.measure.read(bf);
		-- Use calibration to adjust readings
		volts = v0_cal + vm_cal*bf.sourcevalues[i];
		curr = i0_cal + im_cal*bf[i];
		r = volts/curr;
		time = bf.relativetimestamps[i];
	
		-- update rolling average	
		if i > n_filter then
			--rolling variances
			oldV = v0_cal + vm_cal*bf.sourcevalues[i-n_filter]
			oldI = i0_cal + im_cal*bf[i - n_filter]
			oldR = oldV/oldI
			
			meanR = meanR + (r - oldR)/n_filter
			
		
		else
			meanR = meanR*(i-1)/i + r/i
			oldV = volts
	
	    end
		--calc error
		err = resistance_setpoint - meanR	
		-- always track the total voltage incase gains are adjusted
		errSum = errSum + k_i*err*(time - t0)
		-- limit integrator to max value to avoid unstable accumulation
		errSum = band(errSum,source_lbound,source_ubound)
		-- calculate PI loop
		Vk  = k_p*err  + errSum	 --PI control
		
		-- apply voltage
		newSource(Vk,source_lbound,source_ubound)
		
		--iterator
		if buffer.fillmode == 0 then
    		i = i + 1
    	else
            i = nextPosition(i,buffer_size)
        end
        
		t0 = time
		-- send out trigger if condition met
		var = (volts - oldV)^2
		triggered = var >= trigger_var
		if triggered and not last_triggered and trigger_var >0 then trigger.digout[5].assert()end
		last_triggered = triggered
		-- terminate feedback loop if exit conditions met
		if exit_conditions_met(bf,i,buffer_size) then
			break
		end
		display.settext(display.TEXT2,string.format("R = %.2f P = %.2f mW", r,volts*curr*1000))
	end

elseif sensor_type == 'thermistor' then 
	display.settext(display.TEXT1,"Thermistor")
	while (time < duration)
	do
		-- get measurements
		smu.measure.read(bf);
		-- Use calibration to adjust readings
		volts = v0_cal + vm_cal*bf[i];
		curr = i0_cal + im_cal*bf.sourcevalues[i];
		r = volts/curr;
		time = bf.relativetimestamps[i];
	
		-- update rolling average	
		if i > n_filter then
			--rolling variances
			oldV = v0_cal + vm_cal*bf[i-n_filter]
			oldI = i0_cal + im_cal*bf.sourcevalues[i - n_filter]
			oldR = oldV/oldI
			
			meanR = meanR + (r - oldR)/n_filter

		
		else
			meanR = meanR*(i-1)/i + r/i
			oldI = curr
			oldV = volts
	    end
		--calc error
		err = resistance_setpoint - meanR	

		-- always track the total voltage incase gains are adjusted
		errSumOld = errSum
		errSum = errSum - k_i*err*(time - t0)
		-- limit integrator to max value to avoid unstable accumulation
		errSum = band(errSum,errSumOld - max_source_diff ,errSumOld + max_source_diff)
		errSum = band(errSum,source_lbound,source_ubound)
		-- calculate PI loop
		Ik  = -k_p*err  + errSum	 --PI control

		-- apply voltage
		--Ik = band(Ik,curr-max_source_diff,curr+max_source_diff)
		--dig = 100000
		--Ik = math.floor(2*dig*Ik)/(2*dig)
		newSource(Ik,source_lbound,source_ubound)
		--iterator
		i = i + 1
		t0 = time
		-- send out trigger if condition met
		var = (volts - oldV)^2
		triggered = var >= trigger_var
		if triggered and not last_triggered and trigger_var >0 then trigger.digout[5].assert()end
		last_triggered = triggered
		-- terminate feedback loop if exit conditions met
		if exit_conditions_met(bf,i,buffer_size) then
			break
		end
		display.settext(display.TEXT2,string.format("R = %.2f P = %.2f mW", r,volts*curr*1000))
	end
--Put other routines here as else if statement comparing against sesor type
---------------------------------------------------------------------------

--do nothing if no match
------------------------
else
	eventlog.post("sensor not implemented")
end

-----------------
--Finsh Up Script
-----------------
waitcomplete();
display.settext(display.TEXT1,"Free")
display.settext(display.TEXT2,"Waiting Command")
collectgarbage()
print(termination_str)

