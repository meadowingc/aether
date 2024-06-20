dev: install
	watchexec -r -w . --exts lua,tmpl "sleep 1 && make restart-dev"
	make kill-daemon

# ./redbean.com -vmbagd -p 3298 -D ./views/ -D ./static/ -L ./redbean.log -P ./redbean.pid
restart-dev: kill-daemon package
	./redbean.com -vmbagd% -p 3298 -L ./redbean.log -P ./redbean.pid

clean:
	rm redbean.com || true	
	rm redbean.log || true
	rm redbean.pid || true

install-compiled: clean
	mkdir -p .build
	if [ ! -d .build/cosmopolitan ]; then \
		cd .build && git clone https://github.com/jart/cosmopolitan; \
	else \
		cd .build/cosmopolitan && git pull; \
	fi
	cd .build/cosmopolitan && make -j8 MODE=optlinux o/optlinux/tool/net
	cp .build/cosmopolitan/o/optlinux/tool/net/redbean .build/redbean.com

	.build/redbean.com --assimilate
	cp .build/redbean.com .
	
install: clean	
	mkdir -p .build
	if [ ! -f .build/redbean.com ]; then \
		curl https://redbean.dev/redbean-latest.com > .build/redbean.com; \
		chmod +x .build/redbean.com; \
	fi
	cp .build/redbean.com .

# run-rel:
#     sudo ./redbean.com -vvdp80 -p443 -L redbean.log -P redbean.pid

# kill -TERM `cat redbean.pid` 
# kill -TERM `cat redbean.pid` 
kill-daemon:
	killall redbean.com || true
	rm redbean.pid || true
	sleep 2

package:
	zip -r redbean.com .init.lua favicon.ico .lua/ ./views/ ./static/

# meltdown-rel:
# 	kill -USR2 $(cat redbean.pid)

# assimilate:
# 	./redbean.com --assimilate