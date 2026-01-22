function newSource(s,lb,ub)
-- Limits

-- Limit voltage ouput
	if (s > ub)
	then
		s = ub;
	elseif (s < lb)
	then
		s = lb; 		
	end	
-- output voltage

	smu.source.level = s
	return	
	
end

-- next position in queue
function nextPosition(i,bufferSize)
	i = i +1;
	if i > bufferSize
	then
		i = 1;
	end
		

	return i
end

--last position in queue
function lastPosition(i,bufferSize)
	i = i - 1;
	if i < 1
	then
		i = bufferSize;
	end	

	return i
end
--band bass

function band(x,lb,ub)
--band a value between bounds
	if (x > ub)
	then
		x = ub;
	elseif (x < lb)
	then
		x = lb; 		
	end	
	return x
end

function mod(a, b)
    return a - (math.floor(a/b)*b)
end

function exit_conditions_met(buffer,i,buffer_size)
	-- check if a trigger signal was send during script
	out = trigger.wait(0)
	-- if fill once mode on bufffer
	if buffer.fillmode == 0 and i >= buffer_size then
		out = true
	end
	return out
end


