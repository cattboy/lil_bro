https://www.maxon.net/en/tech-info-cinebench?srsltid=AfmBOooiB6U4_kdXpCsuHZ78MHAwPh1oLKrn8c8AOKOPgbD1k4aLC7pY

# Command line options
g_CinebenchCpu1Test=true – runs only the Single Thread test procedure
g_CinebenchCpuSMTTest=true – runs only the Single Core test procedure on a SMT capable core
g_CinebenchCpuXTest=true – runs only the Multiple Threads test procedure
g_CinebenchAllTests=true – runs all test procedures sequentially
g_CinebenchMinimumTestDuration=100 – sets a minimum test duration of 100 seconds
 
## Enable Windows console log, 
- Add an additional command before the Cinebench executable name

start /b /wait "parentconsole" Cinebench.exe g_CinebenchAllTests=true